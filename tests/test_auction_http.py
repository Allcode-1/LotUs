from datetime import timedelta
from uuid import UUID

from app.models.lot import Lot
from app.models.user import UserRole
from app.core.config import settings
from app.services.auction import utc_now
from tests.helpers import (
    assert_error_code,
    create_auction,
    create_item,
    create_user_with_token,
    money,
    start_auction,
    top_up_balance,
)


def test_create_start_bid_and_confirm_lot_sale_happy_path(client, db_session):
    seller, _seller_tokens, seller_headers = create_user_with_token(client, "seller")
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(client, "bidder")
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "auction_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Auction item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = auction["lots"][0]
    assert auction["status"] == "scheduled"
    assert lot["status"] == "pending"
    assert lot["item"]["status"] == "in_auction"

    active_auction = start_auction(client, seller_headers, auction["id"])
    lot = active_auction["lots"][0]
    assert active_auction["status"] == "active"
    assert lot["status"] == "active"

    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")

    bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert bid_response.status_code == 201, bid_response.text
    assert bid_response.json()["bidder_id"] == bidder["id"]
    assert money(bid_response.json()["amount"]) == money("100.00")

    bidder_balance_response = client.get("/api/v1/balance/me", headers=bidder_headers)
    assert bidder_balance_response.status_code == 200, bidder_balance_response.text
    bidder_balance = bidder_balance_response.json()
    assert money(bidder_balance["amount"]) == money("500.00")
    assert money(bidder_balance["reserved_amount"]) == money("100.00")
    assert money(bidder_balance["available_amount"]) == money("400.00")

    sale_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/confirm-sale",
        headers=seller_headers,
    )
    assert sale_response.status_code == 200, sale_response.text
    sold_lot = sale_response.json()
    assert sold_lot["status"] == "sold"
    assert sold_lot["winner_id"] == bidder["id"]
    assert money(sold_lot["sold_price"]) == money("100.00")

    final_auction_response = client.get(
        f"/api/v1/auctions/{auction['id']}",
        headers=seller_headers,
    )
    assert final_auction_response.status_code == 200, final_auction_response.text
    assert final_auction_response.json()["status"] == "finished"

    seller_balance_response = client.get("/api/v1/balance/me", headers=seller_headers)
    assert seller_balance_response.status_code == 200, seller_balance_response.text
    assert money(seller_balance_response.json()["amount"]) == money("100.00")

    bidder_balance_response = client.get("/api/v1/balance/me", headers=bidder_headers)
    assert bidder_balance_response.status_code == 200, bidder_balance_response.text
    bidder_balance = bidder_balance_response.json()
    assert money(bidder_balance["amount"]) == money("400.00")
    assert money(bidder_balance["reserved_amount"]) == money("0.00")

    bidder_items_response = client.get("/api/v1/items/me", headers=bidder_headers)
    assert bidder_items_response.status_code == 200, bidder_items_response.text
    assert [owned_item["id"] for owned_item in bidder_items_response.json()] == [
        item["id"]
    ]

    resale_auction = create_auction(
        client,
        bidder_headers,
        [item["id"]],
        title="Resale auction",
    )
    assert resale_auction["status"] == "scheduled"
    assert resale_auction["seller_id"] == bidder["id"]


def test_auction_creation_rejects_foreign_duplicate_and_locked_items(client):
    _owner, _owner_tokens, owner_headers = create_user_with_token(client, "owner")
    _other, _other_tokens, other_headers = create_user_with_token(client, "other")

    item = create_item(client, owner_headers, title="Locked item")

    foreign_response = client.post(
        "/api/v1/auctions",
        headers=other_headers,
        json={
            "title": "Foreign auction",
            "starts_at": "2030-01-01T12:00:00+00:00",
            "ends_at": "2030-01-01T13:00:00+00:00",
            "min_bid_increment": "5.00",
            "lots": [{"item_id": item["id"], "start_price": "100.00"}],
        },
    )
    assert foreign_response.status_code == 403
    assert_error_code(foreign_response, "item_owner_required")

    duplicate_response = client.post(
        "/api/v1/auctions",
        headers=owner_headers,
        json={
            "title": "Duplicate item auction",
            "starts_at": "2030-01-01T12:00:00+00:00",
            "ends_at": "2030-01-01T13:00:00+00:00",
            "min_bid_increment": "5.00",
            "lots": [
                {"item_id": item["id"], "start_price": "100.00"},
                {"item_id": item["id"], "start_price": "150.00"},
            ],
        },
    )
    assert duplicate_response.status_code == 400
    assert_error_code(duplicate_response, "duplicate_auction_item")

    auction = create_auction(client, owner_headers, [item["id"]])

    second_open_auction_response = client.post(
        "/api/v1/auctions",
        headers=owner_headers,
        json={
            "title": "Second open auction",
            "starts_at": "2030-01-01T12:00:00+00:00",
            "ends_at": "2030-01-01T13:00:00+00:00",
            "min_bid_increment": "5.00",
            "lots": [{"item_id": item["id"], "start_price": "100.00"}],
        },
    )
    assert second_open_auction_response.status_code == 409
    assert_error_code(second_open_auction_response, "item_not_available_for_auction")

    patch_response = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=owner_headers,
        json={"title": "Cannot edit while in auction"},
    )
    assert patch_response.status_code == 409
    assert_error_code(patch_response, "item_not_mutable")

    cancel_response = client.post(
        f"/api/v1/auctions/{auction['id']}/cancel",
        headers=owner_headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"


def test_bid_invariants_for_owner_price_increment_and_reservations(
    client,
    db_session,
):
    seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "bid_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "first_bidder",
    )
    second_bidder, _second_tokens, second_headers = create_user_with_token(
        client,
        "second_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "bid_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Bid item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = start_auction(client, seller_headers, auction["id"])["lots"][0]

    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")
    top_up_balance(client, admin_headers, second_bidder["id"], amount="500.00")

    seller_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=seller_headers,
        json={"amount": "100.00"},
    )
    assert seller_bid_response.status_code == 403
    assert_error_code(seller_bid_response, "seller_bid_forbidden")

    low_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "99.00"},
    )
    assert low_bid_response.status_code == 400
    assert_error_code(low_bid_response, "bid_too_low")

    first_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert first_bid_response.status_code == 201, first_bid_response.text

    same_bidder_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "110.00"},
    )
    assert same_bidder_response.status_code == 409
    assert_error_code(same_bidder_response, "already_highest_bidder")

    too_small_increment_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=second_headers,
        json={"amount": "104.00"},
    )
    assert too_small_increment_response.status_code == 400
    assert_error_code(too_small_increment_response, "bid_too_low")

    second_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=second_headers,
        json={"amount": "105.00"},
    )
    assert second_bid_response.status_code == 201, second_bid_response.text

    first_balance = client.get("/api/v1/balance/me", headers=bidder_headers).json()
    second_balance = client.get("/api/v1/balance/me", headers=second_headers).json()
    assert money(first_balance["reserved_amount"]) == money("0.00")
    assert money(second_balance["reserved_amount"]) == money("105.00")

    lot_model = db_session.get(Lot, UUID(lot["id"]))
    assert lot_model is not None
    closed_bid_time = utc_now() - timedelta(seconds=31)
    lot_model.last_bid_at = closed_bid_time
    lot_model.sale_confirmable_at = closed_bid_time + timedelta(seconds=30)
    db_session.commit()

    closed_window_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "110.00"},
    )
    assert closed_window_response.status_code == 409
    assert_error_code(closed_window_response, "lot_bid_window_closed")


def test_bids_require_active_auction_and_reject_finished_auction(
    client,
    db_session,
):
    _seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "state_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "state_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "state_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="State guarded item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = auction["lots"][0]
    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")

    scheduled_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert scheduled_bid_response.status_code == 409
    assert_error_code(scheduled_bid_response, "auction_not_active")

    start_auction(client, seller_headers, auction["id"])
    finish_response = client.post(
        f"/api/v1/auctions/{auction['id']}/finish",
        headers=seller_headers,
    )
    assert finish_response.status_code == 200, finish_response.text
    assert finish_response.json()["lots"][0]["status"] == "unsold"

    finished_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert finished_bid_response.status_code == 409
    assert_error_code(finished_bid_response, "auction_finished")


def test_lot_min_bid_increment_overrides_auction_increment(
    client,
    db_session,
):
    _seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "custom_increment_seller",
    )
    first_bidder, _first_tokens, first_headers = create_user_with_token(
        client,
        "custom_increment_first",
    )
    second_bidder, _second_tokens, second_headers = create_user_with_token(
        client,
        "custom_increment_second",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "custom_increment_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Custom increment item")
    auction = create_auction(
        client,
        seller_headers,
        [item["id"]],
        min_bid_increment="5.00",
        lot_min_bid_increment="25.00",
    )
    lot = start_auction(client, seller_headers, auction["id"])["lots"][0]
    top_up_balance(client, admin_headers, first_bidder["id"], amount="500.00")
    top_up_balance(client, admin_headers, second_bidder["id"], amount="500.00")

    first_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=first_headers,
        json={"amount": "100.00"},
    )
    assert first_bid_response.status_code == 201, first_bid_response.text

    below_lot_increment_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=second_headers,
        json={"amount": "124.00"},
    )
    assert below_lot_increment_response.status_code == 400
    assert_error_code(below_lot_increment_response, "bid_too_low")

    valid_increment_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=second_headers,
        json={"amount": "125.00"},
    )
    assert valid_increment_response.status_code == 201, valid_increment_response.text

    first_balance = client.get("/api/v1/balance/me", headers=first_headers).json()
    second_balance = client.get("/api/v1/balance/me", headers=second_headers).json()
    assert money(first_balance["reserved_amount"]) == money("0.00")
    assert money(second_balance["reserved_amount"]) == money("125.00")


def test_cancel_auction_with_bid_is_rejected_and_reservation_remains(
    client,
    db_session,
):
    _seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "cancel_bid_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "cancel_bid_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "cancel_bid_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Cancel guarded item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = start_auction(client, seller_headers, auction["id"])["lots"][0]
    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")

    bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert bid_response.status_code == 201, bid_response.text

    cancel_response = client.post(
        f"/api/v1/auctions/{auction['id']}/cancel",
        headers=seller_headers,
    )
    assert cancel_response.status_code == 409
    assert_error_code(cancel_response, "auction_has_bids")

    auction_response = client.get(
        f"/api/v1/auctions/{auction['id']}",
        headers=seller_headers,
    )
    assert auction_response.status_code == 200, auction_response.text
    assert auction_response.json()["status"] == "active"
    assert auction_response.json()["lots"][0]["status"] == "active"

    bidder_balance = client.get("/api/v1/balance/me", headers=bidder_headers).json()
    assert money(bidder_balance["reserved_amount"]) == money("100.00")


def test_confirm_sale_requires_winner_and_cannot_repeat_sale(
    client,
    db_session,
):
    _seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "confirm_guard_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "confirm_guard_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "confirm_guard_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Confirm guarded item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = start_auction(client, seller_headers, auction["id"])["lots"][0]

    no_winner_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/confirm-sale",
        headers=seller_headers,
    )
    assert no_winner_response.status_code == 409
    assert_error_code(no_winner_response, "lot_has_no_winner")

    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")
    bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert bid_response.status_code == 201, bid_response.text

    sale_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/confirm-sale",
        headers=seller_headers,
    )
    assert sale_response.status_code == 200, sale_response.text
    assert sale_response.json()["status"] == "sold"

    repeat_sale_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/confirm-sale",
        headers=seller_headers,
    )
    assert repeat_sale_response.status_code == 409
    assert_error_code(repeat_sale_response, "lot_already_sold")


def test_finish_auction_sells_winning_lots_and_releases_unsold_items(
    client,
    db_session,
):
    seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "finish_mix_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "finish_mix_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "finish_mix_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    sold_item = create_item(client, seller_headers, title="Finish sold item")
    unsold_item = create_item(client, seller_headers, title="Finish unsold item")
    auction = create_auction(
        client,
        seller_headers,
        [sold_item["id"], unsold_item["id"]],
    )
    active_auction = start_auction(client, seller_headers, auction["id"])
    sold_lot = active_auction["lots"][0]
    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")

    bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{sold_lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert bid_response.status_code == 201, bid_response.text

    finish_response = client.post(
        f"/api/v1/auctions/{auction['id']}/finish",
        headers=seller_headers,
    )
    assert finish_response.status_code == 200, finish_response.text
    finished_auction = finish_response.json()
    assert finished_auction["status"] == "finished"

    lots_by_item_id = {lot["item"]["id"]: lot for lot in finished_auction["lots"]}
    sold_lot = lots_by_item_id[sold_item["id"]]
    unsold_lot = lots_by_item_id[unsold_item["id"]]
    assert sold_lot["status"] == "sold"
    assert sold_lot["winner_id"] == bidder["id"]
    assert money(sold_lot["sold_price"]) == money("100.00")
    assert sold_lot["item"]["owner_id"] == bidder["id"]
    assert sold_lot["item"]["status"] == "available"
    assert unsold_lot["status"] == "unsold"
    assert unsold_lot["winner_id"] is None
    assert unsold_lot["item"]["owner_id"] == seller["id"]
    assert unsold_lot["item"]["status"] == "available"

    seller_balance = client.get("/api/v1/balance/me", headers=seller_headers).json()
    bidder_balance = client.get("/api/v1/balance/me", headers=bidder_headers).json()
    assert money(seller_balance["amount"]) == money("100.00")
    assert money(bidder_balance["amount"]) == money("400.00")
    assert money(bidder_balance["reserved_amount"]) == money("0.00")


def test_bid_rate_limit_blocks_excessive_bids(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "bid_user_rate_limit_limit", 1)
    monkeypatch.setattr(settings, "bid_user_rate_limit_window_seconds", 60)

    seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "rate_seller",
    )
    bidder, _bidder_tokens, bidder_headers = create_user_with_token(
        client,
        "rate_bidder",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "rate_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Rate limited bid item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot = start_auction(client, seller_headers, auction["id"])["lots"][0]
    top_up_balance(client, admin_headers, bidder["id"], amount="500.00")

    first_bid_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "100.00"},
    )
    assert first_bid_response.status_code == 201, first_bid_response.text

    limited_response = client.post(
        f"/api/v1/auctions/{auction['id']}/lots/{lot['id']}/bids",
        headers=bidder_headers,
        json={"amount": "105.00"},
    )
    assert limited_response.status_code == 429
    assert_error_code(limited_response, "rate_limit_exceeded")


def test_admin_can_start_and_finish_auction_but_stranger_cannot(
    client,
    db_session,
):
    _seller, _seller_tokens, seller_headers = create_user_with_token(
        client,
        "managed_seller",
    )
    _stranger, _stranger_tokens, stranger_headers = create_user_with_token(
        client,
        "stranger",
    )
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "manage_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, seller_headers, title="Managed item")
    auction = create_auction(client, seller_headers, [item["id"]])

    forbidden_start_response = client.post(
        f"/api/v1/auctions/{auction['id']}/start",
        headers=stranger_headers,
    )
    assert forbidden_start_response.status_code == 403
    assert_error_code(forbidden_start_response, "auction_permission_denied")

    active_auction = start_auction(client, admin_headers, auction["id"])
    assert active_auction["status"] == "active"

    forbidden_finish_response = client.post(
        f"/api/v1/auctions/{auction['id']}/finish",
        headers=stranger_headers,
    )
    assert forbidden_finish_response.status_code == 403
    assert_error_code(forbidden_finish_response, "auction_permission_denied")

    finish_response = client.post(
        f"/api/v1/auctions/{auction['id']}/finish",
        headers=admin_headers,
    )
    assert finish_response.status_code == 200, finish_response.text
    finished_auction = finish_response.json()
    assert finished_auction["status"] == "finished"
    assert finished_auction["lots"][0]["status"] == "unsold"
