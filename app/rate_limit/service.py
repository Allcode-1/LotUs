from dataclasses import dataclass
from hashlib import sha256

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import ServiceUnavailableError, TooManyRequestsError
from app.redis.client import RedisClient


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


class RateLimiter:
    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis

    def check(self, rule: RateLimitRule, identity: str) -> None:
        if not settings.rate_limit_enabled:
            return

        key = self._key(rule, identity)
        try:
            current_count = self.redis.incr(key)
            if current_count == 1:
                self.redis.expire(key, rule.window_seconds)
            ttl = self.redis.ttl(key)
        except RedisError as error:
            if settings.rate_limit_fail_open:
                return
            raise ServiceUnavailableError(
                "Rate limit backend is unavailable",
                code="rate_limit_unavailable",
            ) from error

        retry_after = max(ttl, 1)
        if current_count > rule.limit:
            raise TooManyRequestsError(
                f"Too many requests. Try again in {retry_after} seconds.",
                code="rate_limit_exceeded",
                headers={"Retry-After": str(retry_after)},
            )

    def check_many(self, checks: list[tuple[RateLimitRule, str]]) -> None:
        for rule, identity in checks:
            self.check(rule, identity)

    @staticmethod
    def _key(rule: RateLimitRule, identity: str) -> str:
        identity_hash = sha256(identity.encode("utf-8")).hexdigest()
        return f"lotus:v1:rate:{rule.name}:{identity_hash}"
