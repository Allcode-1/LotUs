from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item_image import ItemImage


def add_item_image(db: Session, values: dict[str, Any]) -> ItemImage:
    image = ItemImage(**values)
    db.add(image)
    db.flush()
    return image


def get_item_images(db: Session, item_id: UUID) -> list[ItemImage]:
    item_images = (
        select(ItemImage)
        .where(ItemImage.item_id == item_id)
        .order_by(ItemImage.sort_order, ItemImage.created_at)
    )
    return list(db.scalars(item_images).all())


def count_item_images(db: Session, item_id: UUID) -> int:
    item_images_count = (
        select(func.count()).select_from(ItemImage).where(ItemImage.item_id == item_id)
    )
    return int(db.scalar(item_images_count) or 0)


def get_item_image(
    db: Session,
    item_id: UUID,
    image_id: UUID,
) -> ItemImage | None:
    item_image = select(ItemImage).where(
        ItemImage.item_id == item_id,
        ItemImage.id == image_id,
    )
    return db.scalar(item_image)


def delete_item_image(db: Session, image: ItemImage) -> None:
    db.delete(image)
    db.flush()
