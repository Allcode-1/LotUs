from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import utils as auth_utils
from app.auth.schemas import TokenPair, UserCreate
from app.auth.tokens import create_access_token, create_refresh_token
from app.models.refresh_session import RefreshSession
from app.models.user import User


def invalid_token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_refresh_payload(refresh_token: str) -> dict:
    try:
        token_payload = auth_utils.decode_jwt(token=refresh_token)
    except InvalidTokenError as error:
        raise invalid_token_error() from error

    if token_payload.get("type") != "refresh":
        raise invalid_token_error()

    if token_payload.get("jti") is None:
        raise invalid_token_error()

    return token_payload


def get_refresh_session(db: Session, jti: str) -> RefreshSession:
    refresh_session = db.scalar(select(RefreshSession).where(RefreshSession.jti == jti))

    if not refresh_session:
        raise invalid_token_error()

    return refresh_session


def create_token_pair(user: User, db: Session) -> TokenPair:
    access_token = create_access_token(user)
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(user)

    refresh_session = RefreshSession(
        jti=refresh_jti,
        user_id=user.id,
        expires_at=refresh_expires_at,
    )

    db.add(refresh_session)
    db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def register_user(payload: UserCreate, db: Session) -> User:
    existing_user = db.scalar(
        select(User).where(
            (User.username == payload.username) | (User.email == payload.email)
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email are already taken",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=auth_utils.hash_password(payload.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(username: str, password: str, db: Session) -> User:
    user = db.scalar(select(User).where(User.username == username))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth_utils.validate_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User inactive",
        )

    return user


def login_user(username: str, password: str, db: Session) -> TokenPair:
    user = authenticate_user(username, password, db)
    return create_token_pair(user, db)


def logout_user(refresh_token: str, db: Session) -> dict[str, str]:
    token_payload = decode_refresh_payload(refresh_token)
    refresh_session = get_refresh_session(db, token_payload["jti"])

    refresh_session.revoked_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Logged out"}


def refresh_tokens(refresh_token: str, db: Session) -> TokenPair:
    token_payload = decode_refresh_payload(refresh_token)
    refresh_session = get_refresh_session(db, token_payload["jti"])

    if refresh_session.revoked_at is not None:
        raise invalid_token_error()

    expires_at = refresh_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if expires_at < now:
        raise invalid_token_error()

    user_id = token_payload.get("sub")

    if user_id is None:
        raise invalid_token_error()

    try:
        user = db.get(User, UUID(user_id))
    except (TypeError, ValueError) as error:
        raise invalid_token_error() from error

    if not user or not user.is_active:
        raise invalid_token_error()

    refresh_session.revoked_at = now

    return create_token_pair(user, db)
