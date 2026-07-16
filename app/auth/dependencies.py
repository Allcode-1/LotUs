from typing import Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth import utils as auth_utils
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.models.user import User, UserRole


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)
AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def invalid_token_error() -> UnauthorizedError:
    return UnauthorizedError(
        "Invalid token",
        code="invalid_token",
        headers=AUTH_HEADERS,
    )


def get_current_token_payload(
    token: str | None = Depends(oauth2_scheme),
) -> dict[str, Any]:
    if token is None:
        raise invalid_token_error()

    try:
        payload = auth_utils.decode_jwt(token=token)
    except InvalidTokenError as error:
        raise invalid_token_error() from error

    if payload.get("type") != "access":
        raise invalid_token_error()

    return payload


def get_current_user(
    payload: dict[str, Any] = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user_id = payload.get("sub")

    if user_id is None:
        raise invalid_token_error()

    try:
        user = db.get(User, UUID(user_id))
    except (TypeError, ValueError) as error:
        raise invalid_token_error() from error

    if not user:
        raise invalid_token_error()

    return user


def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise ForbiddenError("User inactive", code="user_inactive")

    return user


def require_admin(user: User = Depends(get_current_active_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin privileges required", code="admin_required")

    return user
