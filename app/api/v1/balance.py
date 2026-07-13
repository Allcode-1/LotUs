from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.balance import BalanceRead, BalanceUpdate

from app.auth.dependencies import get_current_active_user, require_admin
from app.services.balance import top_up_balance, get_balance

from app.db.session import get_db

router = APIRouter(prefix="/balance", tags=["balance"])


@router.post("/{user_id}", response_model=BalanceRead)
def top_up_balance_router(
    user_id: UUID,
    payload: BalanceUpdate,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)]
):
    
    return top_up_balance(db, user_id, amount=payload.amount)


@router.get("/", response_model=BalanceRead)
def get_balance_router(
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)]
):

    return get_balance(db, user.id)