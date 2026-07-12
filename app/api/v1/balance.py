from uuid import UUID

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.balance import Balance
from app.schemas.balance import BalanceRead, BalanceUpdate

from app.auth.dependencies import get_current_active_user, require_admin
from app.services.balance import top_up_balance, get_balance

from app.db.session import get_db

router = APIRouter(prefix="/balance", tags=["balance"])


@router.post("/{user_id}", response_model=BalanceRead)
def top_up_balance_router(
    user_id: UUID,
    payload: BalanceUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    
    return top_up_balance(db, user_id, amount=payload.amount)


@router.get("/", response_model=BalanceRead)
def get_balance_router(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):

    return get_balance(db, user.id)