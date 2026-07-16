from uuid import UUID

from fastapi import Request

from app.core.config import settings

from .dependencies import get_client_ip
from .service import RateLimiter, RateLimitRule


def check_register_rate_limit(
    rate_limiter: RateLimiter,
    request: Request,
) -> None:
    rate_limiter.check(
        RateLimitRule(
            name="auth_register_ip",
            limit=settings.auth_register_rate_limit_limit,
            window_seconds=settings.auth_register_rate_limit_window_seconds,
        ),
        identity=f"ip:{get_client_ip(request)}",
    )


def check_login_rate_limit(
    rate_limiter: RateLimiter,
    request: Request,
    username: str,
) -> None:
    client_ip = get_client_ip(request)
    normalized_username = username.strip().lower()
    rate_limiter.check_many(
        [
            (
                RateLimitRule(
                    name="auth_login_ip",
                    limit=settings.auth_login_ip_rate_limit_limit,
                    window_seconds=settings.auth_login_ip_rate_limit_window_seconds,
                ),
                f"ip:{client_ip}",
            ),
            (
                RateLimitRule(
                    name="auth_login_username_ip",
                    limit=settings.auth_login_username_rate_limit_limit,
                    window_seconds=settings.auth_login_username_rate_limit_window_seconds,
                ),
                f"username:{normalized_username}:ip:{client_ip}",
            ),
        ]
    )


def check_bid_rate_limit(
    rate_limiter: RateLimiter,
    user_id: UUID,
    auction_id: UUID,
    lot_id: UUID,
) -> None:
    rate_limiter.check_many(
        [
            (
                RateLimitRule(
                    name="bid_user",
                    limit=settings.bid_user_rate_limit_limit,
                    window_seconds=settings.bid_user_rate_limit_window_seconds,
                ),
                f"user:{user_id}",
            ),
            (
                RateLimitRule(
                    name="bid_lot",
                    limit=settings.bid_lot_rate_limit_limit,
                    window_seconds=settings.bid_lot_rate_limit_window_seconds,
                ),
                f"auction:{auction_id}:lot:{lot_id}",
            ),
        ]
    )
