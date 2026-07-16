from typing import Annotated

from fastapi import Depends

from app.redis.client import RedisClient, get_redis

from .auction import AuctionCache
from .base import RedisCache


def get_auction_cache(
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> AuctionCache:
    return AuctionCache(RedisCache(redis))
