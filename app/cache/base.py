import json
import logging
from typing import Any

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.redis.client import RedisClient


logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis

    def get_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        if not settings.cache_enabled:
            return None

        try:
            raw_value = self.redis.get(key)
        except RedisError as error:
            logger.warning(
                "cache backend unavailable on get",
                extra={
                    "event": "cache_unavailable",
                    "operation": "get",
                    "fail_open": settings.cache_fail_open,
                },
            )
            if settings.cache_fail_open:
                return None
            raise ServiceUnavailableError(
                "Cache backend is unavailable",
                code="cache_unavailable",
            ) from error

        if raw_value is None:
            return None
        return json.loads(raw_value)

    def set_json(self, key: str, value: dict[str, Any] | list[Any], ttl: int) -> None:
        if not settings.cache_enabled:
            return

        try:
            self.redis.setex(key, ttl, json.dumps(value))
        except RedisError as error:
            logger.warning(
                "cache backend unavailable on set",
                extra={
                    "event": "cache_unavailable",
                    "operation": "set",
                    "fail_open": settings.cache_fail_open,
                },
            )
            if settings.cache_fail_open:
                return
            raise ServiceUnavailableError(
                "Cache backend is unavailable",
                code="cache_unavailable",
            ) from error

    def delete(self, *keys: str) -> None:
        if not keys:
            return

        try:
            self.redis.delete(*keys)
        except RedisError as error:
            logger.warning(
                "cache backend unavailable on delete",
                extra={
                    "event": "cache_unavailable",
                    "operation": "delete",
                    "fail_open": settings.cache_fail_open,
                },
            )
            if settings.cache_fail_open:
                return
            raise ServiceUnavailableError(
                "Cache backend is unavailable",
                code="cache_unavailable",
            ) from error
