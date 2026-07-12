from sqlalchemy.orm import Session

from app.models.item import Item
from app.repositories import item as item_repository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemNotFoundError(LookupError):
    def __init__(self, item_id: int) -> None:
        super().__init__(f"Item with id={item_id} was not found")


def add_item(db: Session, payload: ItemCreate) -> Item:
    try:
        item = item_repository.add_item(
            db,
            payload.model_dump(),
        )
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


def get_items(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Item]:
    return item_repository.get_items(
        db,
        offset=offset,
        limit=limit,
    )


def get_item(db: Session, item_id: int) -> Item:
    item = item_repository.get_item(db, item_id)
    if item is None:
        raise ItemNotFoundError(item_id)
    return item


def patch_item(
    db: Session,
    item_id: int,
    payload: ItemUpdate,
) -> Item:
    item = get_item(db, item_id)

    try:
        updated_item = item_repository.patch_item(
            db,
            item,
            payload.model_dump(exclude_unset=True),
        )
        db.commit()
        db.refresh(updated_item)
        return updated_item
    except Exception:
        db.rollback()
        raise


def delete_item(db: Session, item_id: int) -> None:
    item = get_item(db, item_id)

    try:
        item_repository.delete_item(db, item)
        db.commit()
    except Exception:
        db.rollback()
        raise
