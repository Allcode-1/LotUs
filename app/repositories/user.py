from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_users(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[User]:
    statement = (
        select(User)
        .order_by(User.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def get_user(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


# def patch_item(
#     db: Session,
#     item: Item,
#     values: dict[str, Any],
# ) -> Item:
#     for field, value in values.items():
#         setattr(item, field, value)

#     db.flush()
#     return item


def delete_item(db: Session, item: Item) -> None:
    db.delete(item)
    db.flush()
