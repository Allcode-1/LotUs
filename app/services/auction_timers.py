import asyncio
from datetime import datetime
from uuid import UUID

from app.db.session import SessionLocal
from app.models.auction import AuctionStatus
from app.schemas.auction import AuctionRead
from app.schemas.auction import LotRead
from app.services import auction as auction_service
from app.ws.auction import auction_ws_manager


async def auto_confirm_lot_sale(
    auction_id: UUID,
    lot_id: UUID,
    expected_confirmable_at: datetime,
) -> None:
    delay = max(
        (
            auction_service.as_utc(expected_confirmable_at) - auction_service.utc_now()
        ).total_seconds(),
        0,
    )
    await asyncio.sleep(delay)

    db = SessionLocal()
    auction: AuctionRead | None = None
    try:
        lot = auction_service.confirm_lot_sale_after_window(
            db,
            auction_id,
            lot_id,
            expected_confirmable_at,
        )
        if lot is not None:
            auction = auction_service.get_auction(db, auction_id)
    finally:
        db.close()

    if lot is None:
        return

    await broadcast_lot_sold(auction_id, lot)
    if auction is not None and auction.status == AuctionStatus.FINISHED:
        await auction_ws_manager.broadcast(
            auction_id,
            {
                "type": "auction_finished",
                "auction": auction.model_dump(mode="json"),
            },
        )


async def broadcast_lot_sold(auction_id: UUID, lot: LotRead) -> None:
    await auction_ws_manager.broadcast(
        auction_id,
        {
            "type": "lot_sold",
            "auction_id": str(auction_id),
            "lot": lot.model_dump(mode="json"),
        },
    )
