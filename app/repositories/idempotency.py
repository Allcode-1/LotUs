from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.idempotency_record import IdempotencyRecord


def add_record(
    db: Session,
    *,
    user_id: UUID,
    operation: str,
    key: str,
    request_hash: str,
    expires_at: datetime,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        user_id=user_id,
        operation=operation,
        key=key,
        request_hash=request_hash,
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()
    return record


def get_record_for_update(
    db: Session,
    *,
    user_id: UUID,
    operation: str,
    key: str,
) -> IdempotencyRecord | None:
    record = (
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
        .with_for_update()
    )
    return db.scalar(record)


def delete_expired_records(db: Session, now: datetime) -> int:
    result = db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < now))
    return int(getattr(result, "rowcount", 0) or 0)
