from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_admin
from app.db.session import get_db
from app.models.balance import Balance
from app.models.user import User
from app.schemas.balance import BalanceRead, BalanceUpdate
from app.services.balance import get_balance, top_up_balance

router = APIRouter(prefix="/balance", tags=["balance"])


@router.get("/me", response_model=BalanceRead)
def get_my_balance(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Balance:
    return get_balance(db, user.id)


@router.post("/users/{user_id}/top-up", response_model=BalanceRead)
def top_up_balance_router(
    user_id: UUID,
    payload: BalanceUpdate,
    _user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Balance:
    return top_up_balance(db, user_id, amount=payload.amount)
