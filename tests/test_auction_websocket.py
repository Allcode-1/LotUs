import pytest
from starlette.websockets import WebSocketDisconnect

from app.models.user import UserRole
from tests.helpers import (
    create_auction,
    create_item,
    create_user_with_token,
    start_auction,
    top_up_balance,
)


def test_websocket_connects_sends_snapshot_and_handles_client_messages(client):
    _seller, seller_tokens, seller_headers = create_user_with_token(
        client,
        "ws_seller",
    )
    item = create_item(client, seller_headers, title="WebSocket snapshot item")
    auction = create_auction(client, seller_headers, [item["id"]])

    url = f"/api/v1/ws/auctions/{auction['id']}?token={seller_tokens['access_token']}"
    with client.websocket_connect(url) as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        assert connected["auction_id"] == auction["id"]

        snapshot = websocket.receive_json()
        assert snapshot["type"] == "auction_snapshot"
        assert snapshot["auction"]["id"] == auction["id"]
        assert snapshot["auction"]["lots"][0]["item"]["id"] == item["id"]

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

        websocket.send_json({"type": "something_else"})
        error = websocket.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "unknown_message_type"


def test_websocket_rejects_invalid_token(client):
    _seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "ws_auth_seller",
    )
    item = create_item(client, seller_headers, title="WebSocket auth item")
    auction = create_auction(client, seller_headers, [item["id"]])

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/v1/ws/auctions/{auction['id']}?token=not-a-token"
        ):
            pass

    assert exc_info.value.code == 1008


def test_websocket_receives_bid_event_from_http_command(client, db_session):
    _seller, seller_tokens, seller_headers = create_user_with_token(
        client,
        "ws_live_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "ws_live_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "ws_live_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="WebSocket live item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = start_auction(client, seller_headers, auction["id"])["lots"][0]
    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")

    url = f"/api/v1/ws/auctions/{auction['id']}?token={seller_tokens['access_token']}"
    with client.websocket_connect(url) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        assert websocket.receive_json()["type"] == "auction_snapshot"

        bid_response = client.post(
            f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
            headers=bidder_headers,
            json={"amount": "100.00"},
        )
        assert bid_response.status_code == 201, bid_response.text

        event = websocket.receive_json()
        assert event["type"] == "bid_placed"
        assert event["auction_id"] == auction["id"]
        assert event["lot"]["id"] == lot["id"]
        assert event["lot"]["winner_id"] == bidder["id"]
        assert event["bid"]["id"] == bid_response.json()["id"]
        assert event["bid"]["bidder_id"] == bidder["id"]
