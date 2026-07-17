import logging
from datetime import timedelta

from sqlalchemy import delete

from app.celery_app import celery_app
from app.core.config import settings
from app.models.refresh_session import RefreshSession
from app.services.auction import utc_now
from app.tasks.db import task_session


logger = logging.getLogger(__name__)


@celery_app.task(name="lotus.cleanup.expired_refresh_sessions")
def cleanup_expired_refresh_sessions_task() -> dict[str, int]:
    cutoff = utc_now() - timedelta(days=settings.refresh_session_cleanup_retention_days)

    with task_session() as db:
        result = db.execute(
            delete(RefreshSession).where(RefreshSession.expires_at < cutoff)
        )
        db.commit()

    deleted_count = int(result.rowcount or 0)
    logger.info(
        "expired refresh sessions cleaned up",
        extra={
            "event": "expired_refresh_sessions_cleaned",
            "deleted_count": deleted_count,
            "retention_days": settings.refresh_session_cleanup_retention_days,
        },
    )
    return {"deleted_count": deleted_count}
