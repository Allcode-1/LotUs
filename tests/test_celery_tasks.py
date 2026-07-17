import app.tasks.auction  # noqa: F401
import app.tasks.cleanup  # noqa: F401
import app.tasks.notifications  # noqa: F401
from app.celery_app import celery_app
from app.core.config import settings
from app.tasks.enqueue import enqueue_task
from app.tasks.notifications import send_registration_email_task


def test_celery_registers_lotus_tasks():
    expected_tasks = {
        "lotus.auctions.auto_confirm_lot_sale",
        "lotus.auctions.sync_lifecycle",
        "lotus.cleanup.expired_refresh_sessions",
        "lotus.notifications.auction_finished_telegram",
        "lotus.notifications.auction_started_telegram",
        "lotus.notifications.registration_email",
    }

    assert expected_tasks.issubset(celery_app.tasks.keys())


def test_enqueue_task_is_noop_when_celery_tasks_are_disabled(monkeypatch):
    monkeypatch.setattr(settings, "celery_tasks_enabled", False)

    result = enqueue_task(send_registration_email_task, "user-id")

    assert result is None
