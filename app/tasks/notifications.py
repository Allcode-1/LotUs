import logging
from uuid import UUID

from app.celery_app import celery_app
from app.tasks.enqueue import enqueue_task


logger = logging.getLogger(__name__)


@celery_app.task(name="lotus.notifications.registration_email")
def send_registration_email_task(user_id: str) -> dict[str, str]:
    logger.info(
        "registration email notification stub",
        extra={
            "event": "registration_email_stub",
            "user_id": user_id,
        },
    )
    return {"status": "stubbed"}


@celery_app.task(name="lotus.notifications.auction_started_telegram")
def send_auction_started_telegram_task(auction_id: str) -> dict[str, str]:
    logger.info(
        "auction started telegram notification stub",
        extra={
            "event": "auction_started_telegram_stub",
            "auction_id": auction_id,
            "reason": "auction_interest_model_not_implemented",
        },
    )
    return {"status": "stubbed"}


@celery_app.task(name="lotus.notifications.auction_finished_telegram")
def send_auction_finished_telegram_task(auction_id: str) -> dict[str, str]:
    logger.info(
        "auction finished telegram notification stub",
        extra={
            "event": "auction_finished_telegram_stub",
            "auction_id": auction_id,
            "reason": "telegram_bot_not_implemented",
        },
    )
    return {"status": "stubbed"}


def enqueue_registration_email(user_id: UUID) -> None:
    enqueue_task(send_registration_email_task, str(user_id))


def enqueue_auction_started_telegram(auction_id: UUID) -> None:
    enqueue_task(send_auction_started_telegram_task, str(auction_id))


def enqueue_auction_finished_telegram(auction_id: UUID) -> None:
    enqueue_task(send_auction_finished_telegram_task, str(auction_id))
