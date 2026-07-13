from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.forms import item_create_form
from app.auth.dependencies import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.item import ItemCreate, ItemImageRead, ItemRead, ItemUpdate
from app.services import item as item_service


router = APIRouter(prefix="/items", tags=["items"])


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
)
def add_item(
    payload: Annotated[ItemCreate, Depends(item_create_form)],
    images: Annotated[list[UploadFile], File(description="1 to 10 item images")],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> ItemRead:
    return item_service.add_item(db, payload, user, images)


@router.get("", response_model=list[ItemRead])
def get_items(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    offset: int = 0,
    limit: int = 100,
) -> list[ItemRead]:
    return item_service.get_items(db, offset, limit)


@router.get("/{item_id}", response_model=ItemRead)
def get_item(
    item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> ItemRead:
    return item_service.get_item(db, item_id)


@router.patch("/{item_id}", response_model=ItemRead)
def patch_item(
    item_id: UUID,
    payload: ItemUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> ItemRead:
    return item_service.patch_item(db, item_id, payload, user)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_item(
    item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    item_service.delete_item(db, item_id, user)


@router.post(
    "/{item_id}/images",
    response_model=list[ItemImageRead],
    status_code=status.HTTP_201_CREATED,
)
def add_item_images(
    item_id: UUID,
    images: Annotated[list[UploadFile], File(description="1 to 10 item images")],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> list[ItemImageRead]:
    return item_service.add_images_to_item(db, item_id, user, images)


@router.get("/{item_id}/images", response_model=list[ItemImageRead])
def get_item_images(
    item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> list[ItemImageRead]:
    return item_service.get_item_images(db, item_id)


@router.delete(
    "/{item_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_item_image(
    item_id: UUID,
    image_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    item_service.delete_item_image(db, item_id, image_id, user)
