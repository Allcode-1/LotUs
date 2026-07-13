from typing import Annotated

from fastapi import APIRouter, Depends, Form, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.auth.dependencies import get_current_active_user, require_admin
from app.auth.schemas import RefreshToken, TokenPair, UserCreate, UserRead
from app.db.session import get_db
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    return auth_service.register_user(payload, db)


@router.post("/login", response_model=TokenPair)
def login_user(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    return auth_service.login_user(username, password, db)


@router.post("/logout")
def logout_user(
    payload: RefreshToken,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    return auth_service.logout_user(payload.refresh_token, db)


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(
    payload: RefreshToken,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    return auth_service.refresh_tokens(payload.refresh_token, db)


@router.get("/users/me", response_model=UserRead)
def get_me(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    return user


@router.get("/users", response_model=list[UserRead])
def get_all_users(
    _user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())
