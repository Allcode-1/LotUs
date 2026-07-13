import os
from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ExternalServiceError, ValidationAppError
from app.models.item import Item
from app.models.item_image import ItemImage
from app.repositories import item_image as item_image_repository
from app.schemas.item import ItemImageRead
from app.services.uploads import UploadFileLike
from app.storage import create_presigned_url, delete_object, upload_fileobj
from app.storage.s3 import StorageError


CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

IMAGE_FORMAT_CONTENT_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class ValidatedImageUpload:
    file: UploadFileLike
    content_type: str
    size_bytes: int
    extension: str


def get_upload_file_size(file: UploadFileLike) -> int:
    try:
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
    except (OSError, ValueError) as error:
        raise ValidationAppError(
            "Unable to read image size",
            code="image_size_unreadable",
        ) from error

    return size


def validate_image_bytes(file: UploadFileLike, content_type: str) -> None:
    try:
        file.file.seek(0)
        with Image.open(file.file) as image:
            image_format = image.format
            image.verify()
            actual_content_type = IMAGE_FORMAT_CONTENT_TYPES.get(image_format or "")
    except (OSError, UnidentifiedImageError) as error:
        raise ValidationAppError(
            "Uploaded file is not a valid image",
            code="invalid_image_file",
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        ) from error
    finally:
        file.file.seek(0)

    if actual_content_type != content_type:
        raise ValidationAppError(
            "Image content does not match declared content type",
            code="image_content_type_mismatch",
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )


def validate_image_files(
    files: Sequence[UploadFileLike],
    existing_count: int = 0,
) -> list[ValidatedImageUpload]:
    if not files:
        raise ValidationAppError(
            "At least one image is required",
            code="image_required",
        )

    total_count = existing_count + len(files)
    if total_count > settings.item_images_max_count:
        raise ValidationAppError(
            f"Item can have at most {settings.item_images_max_count} images",
            code="item_image_limit_exceeded",
        )

    validated_images: list[ValidatedImageUpload] = []

    for file in files:
        content_type = file.content_type or ""
        if content_type not in settings.allowed_item_image_content_types:
            allowed = ", ".join(sorted(settings.allowed_item_image_content_types))
            raise ValidationAppError(
                f"Unsupported image content type. Allowed: {allowed}",
                code="unsupported_image_content_type",
                status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )

        size = get_upload_file_size(file)
        if size <= 0:
            raise ValidationAppError(
                "Image file cannot be empty",
                code="empty_image_file",
            )

        if size > settings.item_image_max_size_bytes:
            raise ValidationAppError(
                f"Image file is too large. Max size is "
                f"{settings.item_image_max_size_bytes} bytes",
                code="image_file_too_large",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        validate_image_bytes(file, content_type)

        validated_images.append(
            ValidatedImageUpload(
                file=file,
                content_type=content_type,
                size_bytes=size,
                extension=CONTENT_TYPE_EXTENSIONS[content_type],
            )
        )

    return validated_images


def build_item_image_storage_key(
    item_id: UUID,
    image_id: UUID,
    extension: str,
) -> str:
    return f"items/{item_id}/images/{image_id}.{extension}"


def delete_uploaded_objects(storage_keys: list[str]) -> None:
    for storage_key in storage_keys:
        try:
            delete_object(storage_key)
        except StorageError:
            continue


def upload_item_image(
    db: Session,
    item: Item,
    upload: ValidatedImageUpload,
    sort_order: int,
) -> ItemImage:
    image_id = uuid4()
    storage_key = build_item_image_storage_key(
        item.id,
        image_id,
        upload.extension,
    )

    upload.file.file.seek(0)
    upload_fileobj(
        upload.file.file,
        storage_key,
        upload.content_type,
    )

    return item_image_repository.add_item_image(
        db,
        {
            "id": image_id,
            "item_id": item.id,
            "storage_key": storage_key,
            "content_type": upload.content_type,
            "size_bytes": upload.size_bytes,
            "is_primary": sort_order == 0,
            "sort_order": sort_order,
        },
    )


def add_item_images(
    db: Session,
    item: Item,
    files: Sequence[UploadFileLike],
) -> tuple[list[ItemImage], list[str]]:
    existing_count = item_image_repository.count_item_images(db, item.id)
    validated_images = validate_image_files(files, existing_count)

    uploaded_storage_keys: list[str] = []
    created_images: list[ItemImage] = []

    try:
        for index, upload in enumerate(validated_images):
            image = upload_item_image(db, item, upload, existing_count + index)
            uploaded_storage_keys.append(image.storage_key)
            created_images.append(image)
    except StorageError as error:
        delete_uploaded_objects(uploaded_storage_keys)
        raise ExternalServiceError(
            "Object storage request failed",
            code="object_storage_error",
        ) from error
    except Exception:
        delete_uploaded_objects(uploaded_storage_keys)
        raise

    return created_images, uploaded_storage_keys


def image_to_read(image: ItemImage) -> ItemImageRead:
    try:
        url = create_presigned_url(image.storage_key)
    except StorageError as error:
        raise ExternalServiceError(
            "Failed to create image URL",
            code="image_url_create_failed",
        ) from error

    return ItemImageRead(
        id=image.id,
        item_id=image.item_id,
        storage_key=image.storage_key,
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        is_primary=image.is_primary,
        sort_order=image.sort_order,
        created_at=image.created_at,
        url=url,
    )
