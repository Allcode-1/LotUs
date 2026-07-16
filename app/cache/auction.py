from uuid import UUID

from app.core.config import settings
from app.schemas.auction import AuctionRead

from .base import RedisCache


class AuctionCache:
    def __init__(self, cache: RedisCache) -> None:
        self.cache = cache

    def get_auction(self, auction_id: UUID) -> AuctionRead | None:
        payload = self.cache.get_json(self._auction_key(auction_id))
        if payload is None:
            return None
        return AuctionRead.model_validate(payload)

    def set_auction(self, auction: AuctionRead) -> None:
        self.cache.set_json(
            self._auction_key(auction.id),
            auction.model_dump(mode="json"),
            settings.auction_cache_ttl_seconds,
        )

    def invalidate_auction(self, auction_id: UUID) -> None:
        self.cache.delete(self._auction_key(auction_id))

    @staticmethod
    def _auction_key(auction_id: UUID) -> str:
        return f"lotus:v1:auctions:{auction_id}:snapshot"
