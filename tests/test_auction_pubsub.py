import asyncio
import json
from uuid import uuid4

from app.core.config import settings
from app.ws.pubsub import publish_auction_event


def test_publish_auction_event_uses_redis_channel(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "ws_pubsub_enabled", True)

    auction_id = uuid4()
    message = {
        "type": "bid_placed",
        "auction_id": str(auction_id),
        "bid": {"amount": "125.00"},
    }

    asyncio.run(publish_auction_event(auction_id, message, fake_redis))

    assert len(fake_redis.publish_calls) == 1
    channel, raw_envelope = fake_redis.publish_calls[0]
    assert channel == settings.ws_pubsub_channel

    envelope = json.loads(raw_envelope)
    assert envelope == {
        "auction_id": str(auction_id),
        "message": message,
    }
