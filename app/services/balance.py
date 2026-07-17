import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.models.balance import Balance
from app.repositories import balance as balance_repository
from app.repositories import user as user_repository


ZERO_MONEY = Decimal("0.00")
logger = logging.getLogger(__name__)


def ensure_user_exists(db: Session, user_id: UUID) -> None:
    if user_repository.get_user(db, user_id) is None:
        raise NotFoundError(
            f"User with id={user_id} was not found",
            code="user_not_found",
        )


def get_or_create_balance_model(
    db: Session,
    user_id: UUID,
    *,
    lock: bool = False,
) -> Balance:
    if lock:
        balance = balance_repository.get_balance_by_user_id_for_update(db, user_id)
    else:
        balance = balance_repository.get_balance_by_user_id(db, user_id)

    if balance is None:
        balance = Balance(
            user_id=user_id,
            amount=ZERO_MONEY,
            reserved_amount=ZERO_MONEY,
        )
        db.add(balance)
        db.flush()

    return balance


def top_up_balance(db: Session, user_id: UUID, amount: Decimal) -> Balance:
    ensure_user_exists(db, user_id)

    if amount <= ZERO_MONEY:
        raise ValidationAppError(
            "Top-up amount must be greater than 0",
            code="invalid_top_up_amount",
        )

    balance = get_or_create_balance_model(db, user_id, lock=True)
    balance.amount += amount

    db.commit()
    db.refresh(balance)

    logger.info(
        "balance topped up",
        extra={
            "event": "balance_topped_up",
            "user_id": str(user_id),
            "amount": str(amount),
            "balance_amount": str(balance.amount),
        },
    )

    return balance


def get_balance(db: Session, user_id: UUID) -> Balance:
    ensure_user_exists(db, user_id)

    balance = balance_repository.get_balance_by_user_id(db, user_id)
    if balance is None:
        balance = get_or_create_balance_model(db, user_id)
        db.commit()
        db.refresh(balance)

    return balance
