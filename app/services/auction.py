import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.models.auction import Auction, AuctionStatus
from app.models.bid import Bid
from app.models.item import Item, ItemStatus
from app.models.lot import Lot, LotStatus
from app.models.user import User, UserRole
from app.repositories import auction as auction_repository
from app.repositories import item as item_repository
from app.schemas.auction import AuctionCreate, AuctionRead, BidCreate, BidRead, LotRead
from app.services import balance as balance_service
from app.services import item as item_service


ZERO_MONEY = Decimal("0.00")
SALE_CONFIRMATION_DELAY_SECONDS = 30
logger = logging.getLogger(__name__)
AUCTIONABLE_ITEM_STATUSES = {ItemStatus.DRAFT, ItemStatus.AVAILABLE}
TERMINAL_LOT_STATUSES = {
    LotStatus.SOLD,
    LotStatus.UNSOLD,
    LotStatus.CANCELLED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_request_datetime_is_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationAppError(
            f"{field_name} must include timezone information",
            code="timezone_required",
        )


def validate_auction_window(payload: AuctionCreate) -> tuple[datetime, datetime]:
    ensure_request_datetime_is_aware(payload.starts_at, "starts_at")
    ensure_request_datetime_is_aware(payload.ends_at, "ends_at")

    starts_at = as_utc(payload.starts_at)
    ends_at = as_utc(payload.ends_at)

    if starts_at >= ends_at:
        raise ValidationAppError(
            "Auction end time must be after start time",
            code="invalid_auction_time_window",
        )

    if ends_at <= utc_now():
        raise ValidationAppError(
            "Auction end time must be in the future",
            code="auction_end_time_in_past",
        )

    return starts_at, ends_at


def validate_pagination(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValidationAppError(
            "Offset must be greater than or equal to 0",
            code="invalid_offset",
        )

    if limit < 1 or limit > 100:
        raise ValidationAppError(
            "Limit must be between 1 and 100",
            code="invalid_limit",
        )


def get_auction_model(db: Session, auction_id: UUID) -> Auction:
    auction = auction_repository.get_auction(db, auction_id)
    if auction is None:
        raise NotFoundError(
            f"Auction with id={auction_id} was not found",
            code="auction_not_found",
        )
    return auction


def get_lot_model(db: Session, lot_id: UUID) -> Lot:
    lot = auction_repository.get_lot(db, lot_id)
    if lot is None:
        raise NotFoundError(
            f"Lot with id={lot_id} was not found",
            code="lot_not_found",
        )
    return lot


def ensure_auction_operator(auction: Auction, user: User) -> None:
    if auction.seller_id != user.id and user.role != UserRole.ADMIN:
        raise ForbiddenError(
            "You do not have permission to manage this auction",
            code="auction_permission_denied",
        )


def ensure_lot_belongs_to_auction(lot: Lot, auction_id: UUID) -> None:
    if lot.auction_id != auction_id:
        raise NotFoundError(
            "Lot was not found in this auction",
            code="lot_not_found",
        )


def validate_create_lots(payload: AuctionCreate) -> list[UUID]:
    item_ids = [lot.item_id for lot in payload.lots]
    if len(set(item_ids)) != len(item_ids):
        raise ValidationAppError(
            "Auction cannot contain the same item more than once",
            code="duplicate_auction_item",
        )
    return item_ids


def validate_items_for_auction(
    items: list[Item], item_ids: list[UUID], user: User
) -> None:
    items_by_id = {item.id: item for item in items}
    missing_item_ids = set(item_ids) - set(items_by_id)

    if missing_item_ids:
        missing = ", ".join(
            str(item_id) for item_id in sorted(missing_item_ids, key=str)
        )
        raise NotFoundError(
            f"Items were not found: {missing}",
            code="auction_item_not_found",
        )

    for item in items:
        if item.owner_id != user.id:
            raise ForbiddenError(
                "Only current item owner can add an item to auction",
                code="item_owner_required",
            )

        if item.status not in AUCTIONABLE_ITEM_STATUSES:
            raise ConflictError(
                "Only available items can be added to auction",
                code="item_not_available_for_auction",
            )


def auction_to_read(auction: Auction) -> AuctionRead:
    return AuctionRead(
        id=auction.id,
        seller_id=auction.seller_id,
        title=auction.title,
        description=auction.description,
        starts_at=auction.starts_at,
        ends_at=auction.ends_at,
        min_bid_increment=auction.min_bid_increment,
        status=auction.status,
        created_at=auction.created_at,
        updated_at=auction.updated_at,
        lots=[
            lot_to_read(lot)
            for lot in sorted(auction.lots, key=lambda lot: lot.lot_number)
        ],
    )


def lot_to_read(lot: Lot) -> LotRead:
    return LotRead(
        id=lot.id,
        auction_id=lot.auction_id,
        item_id=lot.item_id,
        lot_number=lot.lot_number,
        start_price=lot.start_price,
        min_bid_increment=lot.min_bid_increment,
        current_price=lot.current_price,
        winner_id=lot.winner_id,
        last_bid_at=lot.last_bid_at,
        sale_confirmable_at=lot.sale_confirmable_at,
        sold_price=lot.sold_price,
        sold_at=lot.sold_at,
        status=lot.status,
        created_at=lot.created_at,
        updated_at=lot.updated_at,
        item=item_service.item_to_read(lot.item),
    )


def bid_to_read(bid: Bid) -> BidRead:
    return BidRead(
        id=bid.id,
        lot_id=bid.lot_id,
        bidder_id=bid.bidder_id,
        amount=bid.amount,
        created_at=bid.created_at,
    )


def create_auction(db: Session, payload: AuctionCreate, user: User) -> AuctionRead:
    starts_at, ends_at = validate_auction_window(payload)
    item_ids = validate_create_lots(payload)

    try:
        items = item_repository.get_items_by_ids_for_update(db, item_ids)
        validate_items_for_auction(items, item_ids, user)
        items_by_id = {item.id: item for item in items}

        auction = auction_repository.add_auction(
            db,
            {
                "seller_id": user.id,
                "title": payload.title,
                "description": payload.description,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "min_bid_increment": payload.min_bid_increment,
                "status": AuctionStatus.SCHEDULED,
            },
        )

        for index, lot_payload in enumerate(payload.lots, start=1):
            item = items_by_id[lot_payload.item_id]
            auction_repository.add_lot(
                db,
                {
                    "auction_id": auction.id,
                    "item_id": item.id,
                    "lot_number": index,
                    "start_price": lot_payload.start_price,
                    "min_bid_increment": lot_payload.min_bid_increment,
                    "current_price": lot_payload.start_price,
                    "status": LotStatus.PENDING,
                },
            )
            item.status = ItemStatus.IN_AUCTION

        db.commit()
        logger.info(
            "auction created",
            extra={
                "event": "auction_created",
                "auction_id": str(auction.id),
                "seller_id": str(user.id),
                "lots_count": len(payload.lots),
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
            },
        )
        return auction_to_read(get_auction_model(db, auction.id))
    except Exception:
        db.rollback()
        raise


def get_auctions(db: Session, offset: int = 0, limit: int = 100) -> list[AuctionRead]:
    validate_pagination(offset, limit)
    auctions = auction_repository.get_auctions(db, offset=offset, limit=limit)
    return [auction_to_read(auction) for auction in auctions]


def get_my_auctions(
    db: Session,
    user: User,
    offset: int = 0,
    limit: int = 100,
) -> list[AuctionRead]:
    validate_pagination(offset, limit)
    auctions = auction_repository.get_user_auctions(
        db,
        user_id=user.id,
        offset=offset,
        limit=limit,
    )
    return [auction_to_read(auction) for auction in auctions]


def get_auction(db: Session, auction_id: UUID) -> AuctionRead:
    return auction_to_read(get_auction_model(db, auction_id))


def get_lot(db: Session, auction_id: UUID, lot_id: UUID) -> LotRead:
    lot = get_lot_model(db, lot_id)
    ensure_lot_belongs_to_auction(lot, auction_id)
    return lot_to_read(lot)


def start_auction(db: Session, auction_id: UUID, user: User) -> AuctionRead:
    try:
        auction = auction_repository.get_auction_for_update(db, auction_id)
        if auction is None:
            raise NotFoundError(
                f"Auction with id={auction_id} was not found",
                code="auction_not_found",
            )
        ensure_auction_operator(auction, user)

        if auction.status != AuctionStatus.SCHEDULED:
            raise ConflictError(
                "Only scheduled auction can be started",
                code="auction_not_scheduled",
            )

        now = utc_now()
        if now >= as_utc(auction.ends_at):
            raise ConflictError(
                "Auction end time already passed",
                code="auction_ended",
            )

        lots = auction_repository.get_auction_lots_for_update(db, auction.id)
        auction.status = AuctionStatus.ACTIVE
        auction.starts_at = now

        for lot in lots:
            if lot.status == LotStatus.PENDING:
                lot.status = LotStatus.ACTIVE

        db.commit()
        logger.info(
            "auction started",
            extra={
                "event": "auction_started",
                "auction_id": str(auction.id),
                "operator_id": str(user.id),
                "lots_count": len(lots),
            },
        )
        return auction_to_read(get_auction_model(db, auction.id))
    except Exception:
        db.rollback()
        raise


def ensure_auction_accepts_bids(auction: Auction, lot: Lot) -> None:
    if auction.status == AuctionStatus.CANCELLED:
        raise ConflictError("Auction is cancelled", code="auction_cancelled")

    if auction.status == AuctionStatus.FINISHED:
        raise ConflictError("Auction is finished", code="auction_finished")

    if auction.status != AuctionStatus.ACTIVE:
        raise ConflictError(
            "Auction is not active",
            code="auction_not_active",
        )

    now = utc_now()
    starts_at = as_utc(auction.starts_at)
    ends_at = as_utc(auction.ends_at)

    if now < starts_at:
        raise ConflictError(
            "Auction has not started yet",
            code="auction_not_started",
        )

    if now >= ends_at:
        raise ConflictError(
            "Auction has already ended",
            code="auction_ended",
        )

    if lot.status != LotStatus.ACTIVE:
        raise ConflictError(
            "Lot does not accept bids",
            code="lot_not_active",
        )

    if lot.sale_confirmable_at is not None and now >= as_utc(lot.sale_confirmable_at):
        raise ConflictError(
            "Lot sale confirmation window has ended",
            code="lot_bid_window_closed",
        )


def get_required_bid_amount(lot: Lot, auction: Auction) -> Decimal:
    if lot.winner_id is None:
        return lot.start_price

    increment = lot.min_bid_increment or auction.min_bid_increment
    return lot.current_price + increment


def place_bid(
    db: Session,
    auction_id: UUID,
    lot_id: UUID,
    payload: BidCreate,
    bidder: User,
) -> BidRead:
    try:
        lot = auction_repository.get_lot_for_update(db, lot_id)
        if lot is None:
            raise NotFoundError(
                f"Lot with id={lot_id} was not found",
                code="lot_not_found",
            )
        ensure_lot_belongs_to_auction(lot, auction_id)

        auction = lot.auction
        if auction.seller_id == bidder.id:
            raise ForbiddenError(
                "Auction seller cannot bid on own lot",
                code="seller_bid_forbidden",
            )

        ensure_auction_accepts_bids(auction, lot)

        if lot.winner_id == bidder.id:
            raise ConflictError(
                "You are already the highest bidder for this lot",
                code="already_highest_bidder",
            )

        required_amount = get_required_bid_amount(lot, auction)
        if payload.amount < required_amount:
            raise ValidationAppError(
                f"Bid amount must be at least {required_amount}",
                code="bid_too_low",
            )

        bidder_balance = balance_service.get_or_create_balance_model(
            db,
            bidder.id,
            lock=True,
        )
        if bidder_balance.available_amount < payload.amount:
            raise ConflictError(
                "Not enough available balance for this bid",
                code="insufficient_available_balance",
            )

        previous_winner_id = lot.winner_id
        previous_price = lot.current_price
        if lot.winner_id is not None:
            previous_winner_balance = balance_service.get_or_create_balance_model(
                db,
                lot.winner_id,
                lock=True,
            )
            previous_winner_balance.reserved_amount = max(
                ZERO_MONEY,
                previous_winner_balance.reserved_amount - lot.current_price,
            )

        bid_time = utc_now()
        sale_confirmable_at = bid_time + timedelta(
            seconds=SALE_CONFIRMATION_DELAY_SECONDS
        )

        bidder_balance.reserved_amount += payload.amount
        bid = auction_repository.add_bid(
            db,
            {
                "lot_id": lot.id,
                "bidder_id": bidder.id,
                "amount": payload.amount,
            },
        )
        lot.current_price = payload.amount
        lot.winner_id = bidder.id
        lot.last_bid_at = bid_time
        lot.sale_confirmable_at = sale_confirmable_at

        db.commit()
        db.refresh(bid)
        logger.info(
            "bid placed",
            extra={
                "event": "bid_placed",
                "auction_id": str(auction_id),
                "lot_id": str(lot.id),
                "bid_id": str(bid.id),
                "bidder_id": str(bidder.id),
                "amount": str(payload.amount),
                "previous_winner_id": (
                    str(previous_winner_id) if previous_winner_id else None
                ),
                "previous_price": str(previous_price) if previous_winner_id else None,
                "sale_confirmable_at": sale_confirmable_at.isoformat(),
            },
        )
        return bid_to_read(bid)
    except Exception:
        db.rollback()
        raise


def get_lot_bids(
    db: Session,
    auction_id: UUID,
    lot_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[BidRead]:
    validate_pagination(offset, limit)
    lot = get_lot_model(db, lot_id)
    ensure_lot_belongs_to_auction(lot, auction_id)
    bids = auction_repository.get_lot_bids(db, lot_id, offset=offset, limit=limit)
    return [bid_to_read(bid) for bid in bids]


def ensure_lot_can_be_sold(lot: Lot) -> None:
    if lot.status == LotStatus.SOLD:
        raise ConflictError(
            "Lot is already sold",
            code="lot_already_sold",
        )

    if lot.status in {LotStatus.UNSOLD, LotStatus.CANCELLED}:
        raise ConflictError(
            "Lot cannot be sold",
            code="lot_not_sellable",
        )

    if lot.winner_id is None:
        raise ConflictError(
            "Lot has no winning bid",
            code="lot_has_no_winner",
        )


def sell_lot(db: Session, auction: Auction, lot: Lot) -> None:
    ensure_lot_can_be_sold(lot)
    winner_id = lot.winner_id
    if winner_id is None:
        raise ConflictError(
            "Lot has no winning bid",
            code="lot_has_no_winner",
        )

    seller_balance = balance_service.get_or_create_balance_model(
        db,
        auction.seller_id,
        lock=True,
    )
    winner_balance = balance_service.get_or_create_balance_model(
        db,
        winner_id,
        lock=True,
    )
    if winner_balance.reserved_amount < lot.current_price:
        raise ConflictError(
            "Winner balance reservation is inconsistent",
            code="balance_reservation_inconsistent",
        )

    now = utc_now()
    winner_balance.reserved_amount -= lot.current_price
    winner_balance.amount -= lot.current_price
    seller_balance.amount += lot.current_price

    lot.status = LotStatus.SOLD
    lot.sold_price = lot.current_price
    lot.sold_at = now
    lot.item.owner_id = winner_id
    lot.item.status = ItemStatus.AVAILABLE


def finish_auction_if_lots_terminal(auction: Auction, lots: list[Lot]) -> None:
    if all(lot.status in TERMINAL_LOT_STATUSES for lot in lots):
        auction.status = AuctionStatus.FINISHED
        now = utc_now()
        if now < as_utc(auction.ends_at):
            auction.ends_at = now


def confirm_lot_sale(
    db: Session,
    auction_id: UUID,
    lot_id: UUID,
    user: User,
) -> LotRead:
    try:
        auction = auction_repository.get_auction_for_update(db, auction_id)
        if auction is None:
            raise NotFoundError(
                f"Auction with id={auction_id} was not found",
                code="auction_not_found",
            )
        ensure_auction_operator(auction, user)

        lots = auction_repository.get_auction_lots_for_update(db, auction.id)
        lot = next((candidate for candidate in lots if candidate.id == lot_id), None)
        if lot is None:
            raise NotFoundError(
                "Lot was not found in this auction",
                code="lot_not_found",
            )

        sell_lot(db, auction, lot)
        finish_auction_if_lots_terminal(auction, lots)
        was_auction_finished = auction.status == AuctionStatus.FINISHED
        sold_event = {
            "event": "lot_sold",
            "settlement": "manual",
            "auction_id": str(auction.id),
            "lot_id": str(lot.id),
            "seller_id": str(auction.seller_id),
            "winner_id": str(lot.winner_id),
            "sold_price": str(lot.current_price),
        }

        db.commit()
        logger.info("lot sold", extra=sold_event)
        if was_auction_finished:
            logger.info(
                "auction finished",
                extra={
                    "event": "auction_finished",
                    "reason": "all_lots_terminal",
                    "auction_id": str(auction.id),
                    "operator_id": str(user.id),
                },
            )
        return get_lot(db, auction.id, lot.id)
    except Exception:
        db.rollback()
        raise


def confirm_lot_sale_after_window(
    db: Session,
    auction_id: UUID,
    lot_id: UUID,
    expected_confirmable_at: datetime,
) -> LotRead | None:
    try:
        auction = auction_repository.get_auction_for_update(db, auction_id)
        if auction is None or auction.status != AuctionStatus.ACTIVE:
            return None

        lots = auction_repository.get_auction_lots_for_update(db, auction.id)
        lot = next((candidate for candidate in lots if candidate.id == lot_id), None)
        if lot is None or lot.status != LotStatus.ACTIVE or lot.winner_id is None:
            return None

        if lot.sale_confirmable_at is None:
            return None

        current_confirmable_at = as_utc(lot.sale_confirmable_at)
        expected_at = as_utc(expected_confirmable_at)
        if current_confirmable_at > expected_at:
            return None

        if utc_now() < current_confirmable_at:
            return None

        sell_lot(db, auction, lot)
        finish_auction_if_lots_terminal(auction, lots)
        was_auction_finished = auction.status == AuctionStatus.FINISHED
        sold_event = {
            "event": "lot_sold",
            "settlement": "auto_window",
            "auction_id": str(auction.id),
            "lot_id": str(lot.id),
            "seller_id": str(auction.seller_id),
            "winner_id": str(lot.winner_id),
            "sold_price": str(lot.current_price),
        }

        db.commit()
        logger.info("lot sold", extra=sold_event)
        if was_auction_finished:
            logger.info(
                "auction finished",
                extra={
                    "event": "auction_finished",
                    "reason": "all_lots_terminal",
                    "auction_id": str(auction.id),
                    "operator_id": "auto_window",
                },
            )
        return get_lot(db, auction.id, lot.id)
    except Exception:
        db.rollback()
        raise


def cancel_auction(db: Session, auction_id: UUID, user: User) -> AuctionRead:
    try:
        auction = auction_repository.get_auction_for_update(db, auction_id)
        if auction is None:
            raise NotFoundError(
                f"Auction with id={auction_id} was not found",
                code="auction_not_found",
            )
        ensure_auction_operator(auction, user)

        if auction.status == AuctionStatus.FINISHED:
            raise ConflictError(
                "Finished auction cannot be cancelled",
                code="auction_already_finished",
            )

        if auction.status == AuctionStatus.CANCELLED:
            return auction_to_read(get_auction_model(db, auction.id))

        lots = auction_repository.get_auction_lots_for_update(db, auction.id)
        if any(lot.winner_id is not None for lot in lots):
            raise ConflictError(
                "Auction with bids cannot be cancelled",
                code="auction_has_bids",
            )

        auction.status = AuctionStatus.CANCELLED
        for lot in lots:
            lot.status = LotStatus.CANCELLED
            lot.item.status = ItemStatus.AVAILABLE

        db.commit()
        logger.info(
            "auction cancelled",
            extra={
                "event": "auction_cancelled",
                "auction_id": str(auction.id),
                "operator_id": str(user.id),
                "lots_count": len(lots),
            },
        )
        return auction_to_read(get_auction_model(db, auction.id))
    except Exception:
        db.rollback()
        raise


def finish_auction(db: Session, auction_id: UUID, user: User) -> AuctionRead:
    try:
        auction = auction_repository.get_auction_for_update(db, auction_id)
        if auction is None:
            raise NotFoundError(
                f"Auction with id={auction_id} was not found",
                code="auction_not_found",
            )
        ensure_auction_operator(auction, user)

        if auction.status == AuctionStatus.CANCELLED:
            raise ConflictError(
                "Cancelled auction cannot be finished", code="auction_cancelled"
            )

        if auction.status == AuctionStatus.FINISHED:
            return auction_to_read(get_auction_model(db, auction.id))

        if auction.status != AuctionStatus.ACTIVE:
            raise ConflictError(
                "Only active auction can be finished",
                code="auction_not_active",
            )

        lots = auction_repository.get_auction_lots_for_update(db, auction.id)
        sold_count = 0
        unsold_count = 0

        for lot in lots:
            if lot.status in TERMINAL_LOT_STATUSES:
                continue

            if lot.winner_id is None:
                lot.status = LotStatus.UNSOLD
                lot.item.status = ItemStatus.AVAILABLE
                unsold_count += 1
                continue

            sell_lot(db, auction, lot)
            sold_count += 1

        auction.status = AuctionStatus.FINISHED
        now = utc_now()
        if now < as_utc(auction.ends_at):
            auction.ends_at = now

        db.commit()
        logger.info(
            "auction finished",
            extra={
                "event": "auction_finished",
                "reason": "manual_finish",
                "auction_id": str(auction.id),
                "operator_id": str(user.id),
                "sold_count": sold_count,
                "unsold_count": unsold_count,
            },
        )
        return auction_to_read(get_auction_model(db, auction.id))
    except Exception:
        db.rollback()
        raise
