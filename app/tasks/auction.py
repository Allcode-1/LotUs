import asyncio
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache.auction import AuctionCache
from app.cache.base import RedisCache
from app.celery_app import celery_app
from app.core.config import settings
from app.models.auction import Auction, AuctionStatus
from app.models.item import ItemStatus
from app.models.lot import Lot, LotStatus
from app.redis.client import get_redis_client
from app.repositories import auction as auction_repository
from app.schemas.auction import AuctionRead, LotRead
from app.services import auction as auction_service
from app.tasks.db import task_session
from app.tasks.enqueue import enqueue_task
from app.tasks.notifications import (
    enqueue_auction_finished_telegram,
    enqueue_auction_started_telegram,
)
from app.ws.pubsub import publish_auction_event


logger = logging.getLogger(__name__)


def parse_task_datetime(value: str) -> datetime:
    return auction_service.as_utc(datetime.fromisoformat(value))


def publish_auction_event_sync(auction_id: UUID, message: dict) -> None:
    asyncio.run(publish_auction_event(auction_id, message))


def invalidate_auction_cache(auction_id: UUID) -> None:
    try:
        AuctionCache(RedisCache(get_redis_client())).invalidate_auction(auction_id)
    except Exception:
        logger.warning(
            "auction cache invalidation from celery task failed",
            extra={
                "event": "auction_cache_invalidation_task_failed",
                "auction_id": str(auction_id),
            },
            exc_info=True,
        )


def broadcast_lot_sold(auction_id: UUID, lot: LotRead) -> None:
    publish_auction_event_sync(
        auction_id,
        {
            "type": "lot_sold",
            "auction_id": str(auction_id),
            "lot": lot.model_dump(mode="json"),
        },
    )


def broadcast_auction_started(auction: AuctionRead) -> None:
    publish_auction_event_sync(
        auction.id,
        {
            "type": "auction_started",
            "auction": auction.model_dump(mode="json"),
        },
    )


def broadcast_auction_finished(auction: AuctionRead) -> None:
    publish_auction_event_sync(
        auction.id,
        {
            "type": "auction_finished",
            "auction": auction.model_dump(mode="json"),
        },
    )


def enqueue_lot_auto_confirm(
    auction_id: UUID,
    lot_id: UUID,
    expected_confirmable_at: datetime,
) -> None:
    enqueue_task(
        auto_confirm_lot_sale_task,
        str(auction_id),
        str(lot_id),
        auction_service.as_utc(expected_confirmable_at).isoformat(),
        eta=auction_service.as_utc(expected_confirmable_at),
    )


@celery_app.task(name="lotus.auctions.auto_confirm_lot_sale")
def auto_confirm_lot_sale_task(
    auction_id: str,
    lot_id: str,
    expected_confirmable_at: str,
) -> dict[str, object]:
    auction_uuid = UUID(auction_id)
    lot_uuid = UUID(lot_id)
    expected_at = parse_task_datetime(expected_confirmable_at)

    with task_session() as db:
        lot = auction_service.confirm_lot_sale_after_window(
            db,
            auction_uuid,
            lot_uuid,
            expected_at,
        )
        if lot is None:
            logger.info(
                "lot auto-confirm skipped",
                extra={
                    "event": "lot_auto_confirm_skipped",
                    "auction_id": auction_id,
                    "lot_id": lot_id,
                },
            )
            return {"confirmed": False}

        auction = auction_service.get_auction(db, auction_uuid)

    invalidate_auction_cache(auction_uuid)
    broadcast_lot_sold(auction_uuid, lot)
    if auction.status == AuctionStatus.FINISHED:
        broadcast_auction_finished(auction)
        enqueue_auction_finished_telegram(auction_uuid)

    return {
        "confirmed": True,
        "auction_finished": auction.status == AuctionStatus.FINISHED,
    }


@celery_app.task(name="lotus.auctions.sync_lifecycle")
def sync_auction_lifecycle_task() -> dict[str, int]:
    limit = settings.auction_lifecycle_sync_limit
    now = auction_service.utc_now()

    with task_session() as db:
        started = start_due_auctions(db, now, limit)
        confirmed = confirm_due_lot_sales(db, now, limit)
        finished = finish_due_auctions(db, now, limit)

    logger.info(
        "auction lifecycle synchronized",
        extra={
            "event": "auction_lifecycle_synchronized",
            "started_count": len(started),
            "auto_confirmed_count": len(confirmed),
            "finished_count": len(finished),
        },
    )
    return {
        "started_count": len(started),
        "auto_confirmed_count": len(confirmed),
        "finished_count": len(finished),
    }


def start_due_auctions(
    db: Session,
    now: datetime,
    limit: int,
) -> list[AuctionRead]:
    auctions = list(
        db.scalars(
            select(Auction)
            .where(
                Auction.status == AuctionStatus.SCHEDULED,
                Auction.starts_at <= now,
                Auction.ends_at > now,
            )
            .order_by(Auction.starts_at, Auction.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
    )
    if not auctions:
        return []

    started_ids: list[UUID] = []
    for auction in auctions:
        lots = auction_repository.get_auction_lots_for_update(
            db,
            auction.id,
        )
        auction.status = AuctionStatus.ACTIVE
        for lot in lots:
            if lot.status == LotStatus.PENDING:
                lot.status = LotStatus.ACTIVE
        started_ids.append(auction.id)

    db.commit()
    started_auctions = [
        auction_service.get_auction(db, auction_id) for auction_id in started_ids
    ]

    for auction in started_auctions:
        invalidate_auction_cache(auction.id)
        broadcast_auction_started(auction)
        enqueue_auction_started_telegram(auction.id)

    return started_auctions


def confirm_due_lot_sales(
    db: Session,
    now: datetime,
    limit: int,
) -> list[LotRead]:
    due_lots = list(
        db.execute(
            select(Lot.auction_id, Lot.id, Lot.sale_confirmable_at)
            .where(
                Lot.status == LotStatus.ACTIVE,
                Lot.winner_id.is_not(None),
                Lot.sale_confirmable_at.is_not(None),
                Lot.sale_confirmable_at <= now,
            )
            .order_by(Lot.sale_confirmable_at, Lot.id)
            .limit(limit)
        ).all()
    )

    confirmed_lots: list[LotRead] = []
    for auction_id, lot_id, sale_confirmable_at in due_lots:
        if sale_confirmable_at is None:
            continue

        lot = auction_service.confirm_lot_sale_after_window(
            db,
            auction_id,
            lot_id,
            auction_service.as_utc(sale_confirmable_at),
        )
        if lot is None:
            continue

        auction = auction_service.get_auction(db, auction_id)
        invalidate_auction_cache(auction_id)
        broadcast_lot_sold(auction_id, lot)
        if auction.status == AuctionStatus.FINISHED:
            broadcast_auction_finished(auction)
            enqueue_auction_finished_telegram(auction_id)
        confirmed_lots.append(lot)

    return confirmed_lots


def finish_due_auctions(
    db: Session,
    now: datetime,
    limit: int,
) -> list[AuctionRead]:
    auctions = list(
        db.scalars(
            select(Auction)
            .where(
                Auction.status == AuctionStatus.ACTIVE,
                Auction.ends_at <= now,
            )
            .order_by(Auction.ends_at, Auction.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
    )
    if not auctions:
        return []

    finished_ids: list[UUID] = []
    for auction in auctions:
        lots = auction_repository.get_auction_lots_for_update(
            db,
            auction.id,
        )

        for lot in lots:
            if lot.status in auction_service.TERMINAL_LOT_STATUSES:
                continue

            if lot.winner_id is None:
                lot.status = LotStatus.UNSOLD
                lot.item.status = ItemStatus.AVAILABLE
                continue

            auction_service.sell_lot(db, auction, lot)

        auction.status = AuctionStatus.FINISHED
        finished_ids.append(auction.id)

    db.commit()
    finished_auctions = [
        auction_service.get_auction(db, auction_id) for auction_id in finished_ids
    ]

    for auction in finished_auctions:
        invalidate_auction_cache(auction.id)
        broadcast_auction_finished(auction)
        enqueue_auction_finished_telegram(auction.id)

    return finished_auctions
