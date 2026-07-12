from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def encode_jwt(
    payload: dict[str, Any],
    private_key: str | None = None,
    algorithm: str | None = None,
    expire_minutes: int | None = None,
    expire_timedelta: timedelta | None = None,
) -> str:
    key = (
        private_key
        if private_key is not None
        else settings.auth_jwt.private_key_path.read_text(encoding="utf-8")
    )
    token_algorithm = algorithm or settings.auth_jwt.algorithm
    access_expire_minutes = (
        expire_minutes
        if expire_minutes is not None
        else settings.auth_jwt.access_token_expire_minutes
    )

    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expire_timedelta or timedelta(minutes=access_expire_minutes)
    )

    to_encode.update(exp=expire, iat=now)
    return jwt.encode(to_encode, key, algorithm=token_algorithm)


def decode_jwt(
    token: str | bytes,
    public_key: str | None = None,
    algorithm: str | None = None,
) -> dict[str, Any]:
    key = (
        public_key
        if public_key is not None
        else settings.auth_jwt.public_key_path.read_text(encoding="utf-8")
    )
    token_algorithm = algorithm or settings.auth_jwt.algorithm

    decoded = jwt.decode(token, key, algorithms=[token_algorithm])

    if not isinstance(decoded, dict):
        raise InvalidTokenError("Invalid token payload")

    return decoded


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode("utf-8")


def validate_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        password=password.encode(),
        hashed_password=hashed_password.encode("utf-8"),
    )
