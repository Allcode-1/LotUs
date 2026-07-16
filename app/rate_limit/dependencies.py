from typing import Annotated

from fastapi import Depends, Request

from app.redis.client import RedisClient, get_redis

from .service import RateLimiter


def get_rate_limiter(
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> RateLimiter:
    return RateLimiter(redis)


def get_client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host
