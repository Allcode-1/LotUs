from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.auction import Auction, AuctionStatus
from app.models.balance import Balance
from app.models.item_image import ItemImage
from app.models.lot import Lot, LotStatus
from tests.helpers import create_auction, create_item, create_user_with_token


def expect_integrity_error(db_session) -> None:
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_balance_database_constraints_reject_impossible_reservation(
    client,
    db_session,
):
    user, _tokens, _headers = create_user_with_token(client, "balance_invariant")
    balance = db_session.scalar(
        select(Balance).where(Balance.user_id == UUID(user["id"]))
    )
    assert balance is not None

    balance.amount = Decimal("10.00")
    balance.reserved_amount = Decimal("11.00")
    expect_integrity_error(db_session)


def test_lot_database_constraints_reject_price_and_timestamp_inconsistency(
    client,
    db_session,
):
    _seller, _tokens, seller_headers = create_user_with_token(
        client,
        "lot_invariant_seller",
    )
    item = create_item(client, seller_headers, title="Invariant lot item")
    auction = create_auction(client, seller_headers, [item["id"]])
    lot_id = UUID(auction["lots"][0]["id"])

    lot = db_session.get(Lot, lot_id)
    assert lot is not None
    lot.current_price = Decimal("1.00")
    expect_integrity_error(db_session)

    lot = db_session.get(Lot, lot_id)
    assert lot is not None
    lot.sale_confirmable_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    expect_integrity_error(db_session)

    lot = db_session.get(Lot, lot_id)
    assert lot is not None
    lot.sold_price = Decimal("100.00")
    expect_integrity_error(db_session)


def test_item_cannot_be_attached_to_two_open_lots_at_database_boundary(
    client,
    db_session,
):
    seller, _tokens, seller_headers = create_user_with_token(
        client,
        "open_lot_seller",
    )
    item = create_item(client, seller_headers, title="Single open lot item")
    create_auction(client, seller_headers, [item["id"]])

    now = datetime.now(timezone.utc)
    second_auction = Auction(
        seller_id=UUID(seller["id"]),
        title="Second open lot auction",
        starts_at=now + timedelta(minutes=5),
        ends_at=now + timedelta(hours=1),
        min_bid_increment=Decimal("5.00"),
        status=AuctionStatus.SCHEDULED,
    )
    db_session.add(second_auction)
    db_session.flush()
    db_session.add(
        Lot(
            auction_id=second_auction.id,
            item_id=UUID(item["id"]),
            lot_number=1,
            start_price=Decimal("100.00"),
            current_price=Decimal("100.00"),
            status=LotStatus.PENDING,
        )
    )

    expect_integrity_error(db_session)


def test_item_image_database_constraints_reject_duplicate_sort_order(
    client,
    db_session,
):
    _user, _tokens, headers = create_user_with_token(client, "image_invariant_owner")
    item = create_item(client, headers, title="Image invariant item")

    db_session.add(
        ItemImage(
            id=uuid4(),
            item_id=UUID(item["id"]),
            storage_key=f"items/{item['id']}/images/duplicate.png",
            content_type="image/png",
            size_bytes=1,
            is_primary=False,
            sort_order=0,
        )
    )

    expect_integrity_error(db_session)
