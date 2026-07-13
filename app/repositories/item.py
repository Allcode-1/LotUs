from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.item import Item


def add_item(db: Session, values: dict[str, Any]) -> Item:
    item = Item(**values)
    db.add(item)
    db.flush()
    return item


def get_items(
    db: Session,
    offset: int = 0,
    limit: int = 100,
) -> list[Item]:
    items = (
        select(Item)
        .options(selectinload(Item.images))
        .order_by(Item.created_at.desc(), Item.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(items).all())


def get_user_items(
    db: Session,
    user_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[Item]:
    items = (
        select(Item)
        .options(selectinload(Item.images))
        .where(Item.owner_id == user_id)
        .order_by(Item.created_at.desc(), Item.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(items).all())


def get_item(db: Session, item_id: UUID) -> Item | None:
    item = select(Item).options(selectinload(Item.images)).where(Item.id == item_id)
    return db.scalar(item)


def get_items_by_ids_for_update(db: Session, item_ids: list[UUID]) -> list[Item]:
    items = (
        select(Item)
        .options(selectinload(Item.images))
        .where(Item.id.in_(item_ids))
        .with_for_update()
    )
    return list(db.scalars(items).all())


def patch_item(
    db: Session,
    item: Item,
    values: dict[str, Any],
) -> Item:
    for field, value in values.items():
        setattr(item, field, value)

    db.flush()
    return item


def delete_item(db: Session, item: Item) -> None:
    db.delete(item)
    db.flush()
