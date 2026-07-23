import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http import HTTPStatus
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ConflictError, ValidationAppError
from app.models.idempotency_record import (
    IdempotencyRecord,
    IdempotencyRecordStatus,
)
from app.repositories import idempotency as idempotency_repository


MAX_IDEMPOTENCY_KEY_LENGTH = 128


@dataclass(frozen=True)
class IdempotencyReplay:
    response_status_code: int
    response_body: dict[str, Any]


@dataclass(frozen=True)
class IdempotencyClaim:
    record: IdempotencyRecord | None
    replay: IdempotencyReplay | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_idempotency_key(key: str) -> str:
    normalized_key = key.strip()
    if not normalized_key:
        raise ValidationAppError(
            "Idempotency-Key header cannot be empty",
            code="empty_idempotency_key",
        )

    if len(normalized_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValidationAppError(
            f"Idempotency-Key header cannot exceed {MAX_IDEMPOTENCY_KEY_LENGTH} chars",
            code="idempotency_key_too_long",
            status_code=HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
        )

    return normalized_key


def build_request_hash(payload: Mapping[str, Any]) -> str:
    serialized_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(serialized_payload.encode("utf-8")).hexdigest()


def build_expires_at() -> datetime:
    return utc_now() + timedelta(seconds=settings.idempotency_key_ttl_seconds)


def is_expired(record: IdempotencyRecord) -> bool:
    return as_utc(record.expires_at) <= utc_now()


def replay_or_conflict(
    record: IdempotencyRecord,
    request_hash: str,
) -> IdempotencyReplay:
    if record.request_hash != request_hash:
        raise ConflictError(
            "Idempotency key was already used with a different request",
            code="idempotency_key_conflict",
        )

    if record.status != IdempotencyRecordStatus.COMPLETED.value:
        raise ConflictError(
            "Request with this idempotency key is already in progress",
            code="idempotency_key_in_progress",
        )

    if record.response_status_code is None or record.response_body is None:
        raise ConflictError(
            "Idempotency record is incomplete",
            code="idempotency_record_incomplete",
        )

    return IdempotencyReplay(
        response_status_code=record.response_status_code,
        response_body=record.response_body,
    )


def claim_idempotency_key(
    db: Session,
    *,
    user_id: UUID,
    operation: str,
    key: str,
    request_hash: str,
) -> IdempotencyClaim:
    normalized_key = normalize_idempotency_key(key)
    record = idempotency_repository.get_record_for_update(
        db,
        user_id=user_id,
        operation=operation,
        key=normalized_key,
    )

    if record is not None:
        if not is_expired(record):
            return IdempotencyClaim(
                record=None,
                replay=replay_or_conflict(record, request_hash),
            )

        db.delete(record)
        db.flush()

    try:
        record = idempotency_repository.add_record(
            db,
            user_id=user_id,
            operation=operation,
            key=normalized_key,
            request_hash=request_hash,
            expires_at=build_expires_at(),
        )
    except IntegrityError:
        db.rollback()
        record = idempotency_repository.get_record_for_update(
            db,
            user_id=user_id,
            operation=operation,
            key=normalized_key,
        )
        if record is None:
            return claim_idempotency_key(
                db,
                user_id=user_id,
                operation=operation,
                key=normalized_key,
                request_hash=request_hash,
            )
        return IdempotencyClaim(
            record=None,
            replay=replay_or_conflict(record, request_hash),
        )

    return IdempotencyClaim(record=record)


def get_replay(
    db: Session,
    *,
    user_id: UUID,
    operation: str,
    key: str,
    request_hash: str,
) -> IdempotencyReplay | None:
    normalized_key = normalize_idempotency_key(key)
    record = idempotency_repository.get_record_for_update(
        db,
        user_id=user_id,
        operation=operation,
        key=normalized_key,
    )
    if record is None or is_expired(record):
        return None

    return replay_or_conflict(record, request_hash)


def complete_record(
    record: IdempotencyRecord,
    *,
    response_status_code: int,
    response_body: dict[str, Any],
) -> None:
    record.status = IdempotencyRecordStatus.COMPLETED.value
    record.response_status_code = response_status_code
    record.response_body = response_body
