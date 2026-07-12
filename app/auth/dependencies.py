from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth import utils as auth_utils
from app.db.session import get_db
from app.models.user import User, UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def invalid_token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User inactive",
        )

    return user


def require_admin(user: User = Depends(get_current_active_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return user
