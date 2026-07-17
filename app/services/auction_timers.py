from datetime import datetime
from uuid import UUID

from app.schemas.auction import LotRead
from app.tasks.auction import enqueue_lot_auto_confirm
from app.ws.pubsub import publish_auction_event


async def auto_confirm_lot_sale(
    auction_id: UUID,
    lot_id: UUID,
    expected_confirmable_at: datetime,
) -> None:
    enqueue_lot_auto_confirm(auction_id, lot_id, expected_confirmable_at)


async def broadcast_lot_sold(auction_id: UUID, lot: LotRead) -> None:
    await publish_auction_event(
        auction_id,
        {
            "type": "lot_sold",
            "auction_id": str(auction_id),
            "lot": lot.model_dump(mode="json"),
        },
    )
