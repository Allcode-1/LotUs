from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.models.item import Item, ItemStatus
from app.models.user import User
from app.repositories import item as item_repository
from app.repositories import item_image as item_image_repository
from app.schemas.item import ItemCreate, ItemImageRead, ItemRead, ItemUpdate
from app.services import item_image as item_image_service
from app.services.uploads import UploadFileLike
from app.storage import delete_object
from app.storage.s3 import StorageError


MUTABLE_ITEM_STATUSES = {ItemStatus.DRAFT, ItemStatus.AVAILABLE}


def get_item_model(db: Session, item_id: UUID) -> Item:
    item = item_repository.get_item(db, item_id)
    if item is None:
        raise NotFoundError(
            f"Item with id={item_id} was not found",
            code="item_not_found",
        )

    return item


def ensure_item_owner(item: Item, user: User) -> None:
    if item.owner_id != user.id:
        raise ForbiddenError(
            "You do not have permission to modify this item",
            code="item_permission_denied",
        )


def ensure_item_mutable(item: Item) -> None:
    if item.status not in MUTABLE_ITEM_STATUSES:
        raise ConflictError(
            "Only available items can be changed",
            code="item_not_mutable",
        )


def item_to_read(item: Item) -> ItemRead:
    return ItemRead(
        id=item.id,
        title=item.title,
        description=item.description,
        creator_id=item.creator_id,
        owner_id=item.owner_id,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
        images=[item_image_service.image_to_read(image) for image in item.images],
    )


def validate_pagination(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValidationAppError(
            "Offset must be greater than or equal to 0",
            code="invalid_offset",
        )

    if limit < 1 or limit > 100:
        raise ValidationAppError(
            "Limit must be between 1 and 100",
            code="invalid_limit",
        )


def add_item(
    db: Session,
    payload: ItemCreate,
    user: User,
    images: Sequence[UploadFileLike],
) -> ItemRead:
    uploaded_storage_keys: list[str] = []

    try:
        item = item_repository.add_item(
            db,
            {
                **payload.model_dump(),
                "creator_id": user.id,
                "owner_id": user.id,
                "status": ItemStatus.AVAILABLE,
            },
        )
        _, uploaded_storage_keys = item_image_service.add_item_images(db, item, images)

        db.commit()
        return item_to_read(get_item_model(db, item.id))
    except Exception:
        db.rollback()
        item_image_service.delete_uploaded_objects(uploaded_storage_keys)
        raise


def get_items(
    db: Session,
    offset: int = 0,
    limit: int = 100,
) -> list[ItemRead]:
    validate_pagination(offset, limit)

    items = item_repository.get_items(
        db,
        offset=offset,
        limit=limit,
    )
    return [item_to_read(item) for item in items]


def get_my_items(
    db: Session,
    user: User,
    offset: int = 0,
    limit: int = 100,
) -> list[ItemRead]:
    validate_pagination(offset, limit)

    items = item_repository.get_user_items(
        db,
        user_id=user.id,
        offset=offset,
        limit=limit,
    )
    return [item_to_read(item) for item in items]


def get_item(db: Session, item_id: UUID) -> ItemRead:
    return item_to_read(get_item_model(db, item_id))


def patch_item(
    db: Session,
    item_id: UUID,
    payload: ItemUpdate,
    user: User,
) -> ItemRead:
    item = get_item_model(db, item_id)
    ensure_item_owner(item, user)
    ensure_item_mutable(item)

    try:
        updated_item = item_repository.patch_item(
            db,
            item,
            payload.model_dump(exclude_unset=True),
        )
        db.commit()
        return item_to_read(get_item_model(db, updated_item.id))
    except Exception:
        db.rollback()
        raise


def delete_storage_objects(storage_keys: list[str]) -> None:
    for storage_key in storage_keys:
        try:
            delete_object(storage_key)
        except StorageError:
            continue


def delete_item(
    db: Session,
    item_id: UUID,
    user: User,
) -> None:
    item = get_item_model(db, item_id)
    ensure_item_owner(item, user)
    ensure_item_mutable(item)

    storage_keys = [image.storage_key for image in item.images]

    try:
        item_repository.delete_item(db, item)
        db.commit()
    except Exception:
        db.rollback()
        raise

    delete_storage_objects(storage_keys)


def add_images_to_item(
    db: Session,
    item_id: UUID,
    user: User,
    images: Sequence[UploadFileLike],
) -> list[ItemImageRead]:
    item = get_item_model(db, item_id)
    ensure_item_owner(item, user)
    ensure_item_mutable(item)

    uploaded_storage_keys: list[str] = []

    try:
        created_images, uploaded_storage_keys = item_image_service.add_item_images(
            db,
            item,
            images,
        )
        db.commit()
    except Exception:
        db.rollback()
        item_image_service.delete_uploaded_objects(uploaded_storage_keys)
        raise

    created_image_ids = {image.id for image in created_images}
    item_images = item_image_repository.get_item_images(db, item.id)

    return [
        item_image_service.image_to_read(image)
        for image in item_images
        if image.id in created_image_ids
    ]


def get_item_images(db: Session, item_id: UUID) -> list[ItemImageRead]:
    item = get_item_model(db, item_id)
    item_images = item_image_repository.get_item_images(db, item.id)

    return [item_image_service.image_to_read(image) for image in item_images]


def delete_item_image(
    db: Session,
    item_id: UUID,
    image_id: UUID,
    user: User,
) -> None:
    item = get_item_model(db, item_id)
    ensure_item_owner(item, user)
    ensure_item_mutable(item)

    image = item_image_repository.get_item_image(
        db,
        item_id=item.id,
        image_id=image_id,
    )
    if image is None:
        raise NotFoundError(
            f"Item image with id={image_id} was not found",
            code="item_image_not_found",
        )

    storage_key = image.storage_key

    try:
        item_image_repository.delete_item_image(db, image)
        db.commit()
    except Exception:
        db.rollback()
        raise

    delete_storage_objects([storage_key])
