import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from redis.exceptions import RedisError

from app.core.config import settings
from app.redis.client import RedisClient, get_redis_client
from app.ws.auction import auction_ws_manager


logger = logging.getLogger(__name__)


def build_auction_event_envelope(auction_id: UUID, message: dict[str, Any]) -> str:
    return json.dumps(
        {
            "auction_id": str(auction_id),
            "message": message,
        },
        default=str,
    )


async def publish_auction_event(
    auction_id: UUID,
    message: dict[str, Any],
    redis_client: RedisClient | None = None,
) -> None:
    if not settings.ws_pubsub_enabled:
        await auction_ws_manager.broadcast(auction_id, message)
        return

    envelope = build_auction_event_envelope(auction_id, message)
    redis = redis_client or get_redis_client()

    try:
        subscribers_count = await asyncio.to_thread(
            redis.publish,
            settings.ws_pubsub_channel,
            envelope,
        )
        logger.info(
            "auction websocket event published",
            extra={
                "event": "auction_ws_event_published",
                "auction_id": str(auction_id),
                "message_type": message.get("type"),
                "subscribers_count": subscribers_count,
            },
        )
    except RedisError:
        logger.warning(
            "auction websocket pubsub publish failed",
            extra={
                "event": "auction_ws_pubsub_publish_failed",
                "auction_id": str(auction_id),
                "message_type": message.get("type"),
                "local_fallback": settings.ws_pubsub_local_fallback,
            },
            exc_info=True,
        )
        if settings.ws_pubsub_local_fallback:
            await auction_ws_manager.broadcast(auction_id, message)


class AuctionPubSubListener:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start(self) -> None:
        if not settings.ws_pubsub_enabled:
            logger.info(
                "auction websocket pubsub disabled",
                extra={"event": "auction_ws_pubsub_disabled"},
            )
            return

        if self._task is not None and not self._task.done():
            return

        self._stopping = False
        self._task = asyncio.create_task(
            self._run(),
            name="auction-ws-pubsub-listener",
        )

    async def stop(self) -> None:
        self._stopping = True
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while not self._stopping:
            pubsub = None
            try:
                redis = get_redis_client()
                pubsub = redis.pubsub()
                await asyncio.to_thread(pubsub.subscribe, settings.ws_pubsub_channel)
                logger.info(
                    "auction websocket pubsub listener started",
                    extra={
                        "event": "auction_ws_pubsub_listener_started",
                        "channel": settings.ws_pubsub_channel,
                    },
                )

                while not self._stopping:
                    message = await asyncio.to_thread(
                        pubsub.get_message,
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message is None:
                        continue

                    await handle_pubsub_message(message)
            except asyncio.CancelledError:
                raise
            except RedisError:
                logger.warning(
                    "auction websocket pubsub listener unavailable",
                    extra={
                        "event": "auction_ws_pubsub_listener_unavailable",
                        "channel": settings.ws_pubsub_channel,
                        "reconnect_delay_seconds": (
                            settings.ws_pubsub_reconnect_delay_seconds
                        ),
                    },
                    exc_info=True,
                )
                await asyncio.sleep(settings.ws_pubsub_reconnect_delay_seconds)
            except Exception:
                logger.exception(
                    "auction websocket pubsub listener failed",
                    extra={
                        "event": "auction_ws_pubsub_listener_failed",
                        "channel": settings.ws_pubsub_channel,
                        "reconnect_delay_seconds": (
                            settings.ws_pubsub_reconnect_delay_seconds
                        ),
                    },
                )
                await asyncio.sleep(settings.ws_pubsub_reconnect_delay_seconds)
            finally:
                if pubsub is not None:
                    try:
                        await asyncio.to_thread(pubsub.close)
                    except RedisError:
                        logger.warning(
                            "auction websocket pubsub close failed",
                            extra={
                                "event": "auction_ws_pubsub_close_failed",
                                "channel": settings.ws_pubsub_channel,
                            },
                            exc_info=True,
                        )


async def handle_pubsub_message(message: dict[str, Any]) -> None:
    raw_data = message.get("data")
    if isinstance(raw_data, bytes):
        raw_data = raw_data.decode("utf-8")

    if not isinstance(raw_data, str):
        logger.warning(
            "auction websocket pubsub message ignored",
            extra={
                "event": "auction_ws_pubsub_message_ignored",
                "reason": "invalid_data_type",
            },
        )
        return

    try:
        envelope = json.loads(raw_data)
        auction_id = UUID(envelope["auction_id"])
        payload = envelope["message"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning(
            "auction websocket pubsub message ignored",
            extra={
                "event": "auction_ws_pubsub_message_ignored",
                "reason": "invalid_envelope",
            },
        )
        return

    if not isinstance(payload, dict):
        logger.warning(
            "auction websocket pubsub message ignored",
            extra={
                "event": "auction_ws_pubsub_message_ignored",
                "reason": "invalid_payload",
            },
        )
        return

    await auction_ws_manager.broadcast(auction_id, payload)
    logger.info(
        "auction websocket event delivered locally",
        extra={
            "event": "auction_ws_event_delivered",
            "auction_id": str(auction_id),
            "message_type": payload.get("type"),
        },
    )


auction_pubsub_listener = AuctionPubSubListener()
