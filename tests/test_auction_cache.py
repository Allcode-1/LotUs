from app.services import auction_query as auction_query_service
from tests.helpers import (
    create_auction,
    create_item,
    create_user_with_token,
    start_auction,
)


def test_get_auction_uses_cache_aside(client, fake_redis, monkeypatch):
    _seller, _tokens, seller_headers = create_user_with_token(
        client,
        "cache_seller",
    )
    item = create_item(client, seller_headers, title="Cached item")
    auction = create_auction(client, seller_headers, [item["id"]])

    first_response = client.get(
        f"/api/v1/auctions/{auction['id']}",
        headers=seller_headers,
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["id"] == auction["id"]
    assert len(fake_redis.setex_calls) == 1

    def fail_if_database_is_used(*args, **kwargs):
        raise AssertionError("Expected auction snapshot to be served from cache")

    monkeypatch.setattr(
        auction_query_service.auction_service,
        "get_auction",
        fail_if_database_is_used,
    )

    second_response = client.get(
        f"/api/v1/auctions/{auction['id']}",
        headers=seller_headers,
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.json()["id"] == auction["id"]


def test_auction_mutation_invalidates_cached_snapshot(client, fake_redis):
    _seller, _tokens, seller_headers = create_user_with_token(
        client,
        "cache_invalidation_seller",
    )
    item = create_item(client, seller_headers, title="Cache invalidation item")
    auction = create_auction(client, seller_headers, [item["id"]])

    cached_response = client.get(
        f"/api/v1/auctions/{auction['id']}",
        headers=seller_headers,
    )
    assert cached_response.status_code == 200, cached_response.text
    assert cached_response.json()["status"] == "scheduled"

    start_auction(client, seller_headers, auction["id"])
    assert fake_redis.delete_calls

    refreshed_response = client.get(
        f"/api/v1/auctions/{auction['id']}",
        headers=seller_headers,
    )
    assert refreshed_response.status_code == 200, refreshed_response.text
    assert refreshed_response.json()["status"] == "active"
