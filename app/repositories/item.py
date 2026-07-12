from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item


def add_item(db: Session, values: dict[str, Any]) -> Item:
    item = Item(**values)
    db.add(item)
    db.flush()
    return item


def get_items(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Item]:
    statement = (
        select(Item)
        .order_by(Item.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def get_item(db: Session, item_id: int) -> Item | None:
    return db.get(Item, item_id)


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
