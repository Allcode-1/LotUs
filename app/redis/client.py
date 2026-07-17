from functools import lru_cache
from typing import Any, Protocol

from redis import Redis

from app.core.config import settings


class RedisClient(Protocol):
    def get(self, name: str) -> str | None: ...

    def setex(self, name: str, time: int, value: str) -> bool: ...

    def delete(self, *names: str) -> int: ...

    def incr(self, name: str) -> int: ...

    def expire(self, name: str, time: int) -> bool: ...

    def ttl(self, name: str) -> int: ...

    def publish(self, channel: str, message: str) -> int: ...

    def pubsub(self) -> Any: ...


@lru_cache
def get_redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
    )


def get_redis() -> RedisClient:
    return get_redis_client()
