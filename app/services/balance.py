from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.balance import Balance
from app.repositories.balance import get_balance_by_user_id

def top_up_balance(db: Session, user_id: UUID, amount: Decimal) -> Balance:
    
    balance = get_balance_by_user_id(db, user_id)
    
    if balance is None:
        balance = Balance(
            user_id=user_id,
            amount=Decimal("0.00"),
        )
        db.add(balance)

    balance.amount += amount

    db.commit()
    db.refresh(balance)

    return balance


def get_balance(db: Session, user_id: UUID) -> Balance:
    
    balance = get_balance_by_user_id(db, user_id)
    return balance

