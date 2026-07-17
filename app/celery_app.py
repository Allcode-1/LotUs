from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging


configure_logging(settings.log_level, settings.log_format)

celery_app = Celery(
    "lotus",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend or None,
    include=[
        "app.tasks.auction",
        "app.tasks.cleanup",
        "app.tasks.notifications",
    ],
)

celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=settings.celery_broker_connection_timeout_seconds,
    enable_utc=True,
    result_serializer="json",
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_eager_propagates,
    task_serializer="json",
    timezone="UTC",
)

celery_app.conf.beat_schedule = {
    "sync-auction-lifecycle": {
        "task": "lotus.auctions.sync_lifecycle",
        "schedule": settings.auction_lifecycle_sync_interval_seconds,
    },
    "cleanup-expired-refresh-sessions": {
        "task": "lotus.cleanup.expired_refresh_sessions",
        "schedule": settings.cleanup_interval_seconds,
    },
}
