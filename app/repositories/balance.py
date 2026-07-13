from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.balance import Balance


def get_balance_by_user_id(db: Session, user_id: UUID) -> Balance | None:
    balance = select(Balance).where(Balance.user_id == user_id)
    return db.scalar(balance)


def get_balance_by_user_id_for_update(db: Session, user_id: UUID) -> Balance | None:
    balance = select(Balance).where(Balance.user_id == user_id).with_for_update()
    return db.scalar(balance)
