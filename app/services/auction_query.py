from uuid import UUID

from sqlalchemy.orm import Session

from app.cache.auction import AuctionCache
from app.schemas.auction import AuctionRead
from app.services import auction as auction_service


def get_auction(
    db: Session,
    auction_cache: AuctionCache,
    auction_id: UUID,
) -> AuctionRead:
    cached_auction = auction_cache.get_auction(auction_id)
    if cached_auction is not None:
        return cached_auction

    auction = auction_service.get_auction(db, auction_id)
    auction_cache.set_auction(auction)
    return auction
