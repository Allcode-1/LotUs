import logging
from datetime import datetime
from typing import Any

from celery import Task
from celery.result import AsyncResult
from kombu.exceptions import OperationalError

from app.core.config import settings


logger = logging.getLogger(__name__)


def enqueue_task(
    task: Task,
    *args: Any,
    eta: datetime | None = None,
    **kwargs: Any,
) -> AsyncResult | None:
    if not settings.celery_tasks_enabled:
        logger.info(
            "celery task skipped",
            extra={
                "event": "celery_task_skipped",
                "task_name": task.name,
                "reason": "disabled",
            },
        )
        return None

    try:
        return task.apply_async(args=args, kwargs=kwargs, eta=eta)
    except OperationalError:
        logger.warning(
            "celery task enqueue failed",
            extra={
                "event": "celery_task_enqueue_failed",
                "task_name": task.name,
                "reason": "broker_unavailable",
            },
            exc_info=True,
        )
        return None
