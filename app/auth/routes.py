from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.auth.dependencies import get_current_active_user, require_admin
from app.auth.schemas import RefreshToken, TokenPair, UserCreate, UserRead
from app.db.session import get_db
from app.models.user import User
from app.rate_limit import policies as rate_limit_policies
from app.rate_limit.dependencies import get_rate_limiter
from app.rate_limit.service import RateLimiter
from app.tasks.notifications import enqueue_registration_email


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> User:
    rate_limit_policies.check_register_rate_limit(rate_limiter, request)
    user = auth_service.register_user(payload, db)
    background_tasks.add_task(enqueue_registration_email, user.id)
    return user


@router.post("/login", response_model=TokenPair)
def login_user(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> TokenPair:
    rate_limit_policies.check_login_rate_limit(rate_limiter, request, username)
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
