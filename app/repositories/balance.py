from typing import Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.balance import Balance


# def increase_balance(db: Session, amount: Decimal) -> Balance:
#     balance = Decimal
#     db.add(balance)
#     db.flush()
#     return item


# def get_items(
#     db: Session,
#     *,
#     offset: int = 0,
#     limit: int = 100,
# ) -> list[Item]:
#     statement = (
#         select(Item)
#         .order_by(Item.id)
#         .offset(offset)
#         .limit(limit)
#     )
#     return list(db.scalars(statement).all())


def get_balance_by_user_id(db: Session, user_id: UUID) -> Balance | None:
    return db.scalar(
        select(Balance).where(Balance.user_id == user_id)
    )


# def patch_item(
#     db: Session,
#     item: Item,
#     values: dict[str, Any],
# ) -> Item:
#     for field, value in values.items():
#         setattr(item, field, value)

#     db.flush()
#     return item


# def delete_item(db: Session, item: Item) -> None:
#     db.delete(item)
#     db.flush()
