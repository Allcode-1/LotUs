from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.auction import Auction
from app.models.bid import Bid
from app.models.item import Item
from app.models.lot import Lot


def add_auction(db: Session, values: dict[str, Any]) -> Auction:
    auction = Auction(**values)
    db.add(auction)
    db.flush()
    return auction


def add_lot(db: Session, values: dict[str, Any]) -> Lot:
    lot = Lot(**values)
    db.add(lot)
    db.flush()
    return lot


def add_bid(db: Session, values: dict[str, Any]) -> Bid:
    bid = Bid(**values)
    db.add(bid)
    db.flush()
    return bid


def auction_load_options():
    return (
        selectinload(Auction.lots).selectinload(Lot.item).selectinload(Item.images),
    )


def lot_load_options():
    return (
        joinedload(Lot.auction),
        joinedload(Lot.item).selectinload(Item.images),
    )


def get_auctions(
    db: Session,
    offset: int = 0,
    limit: int = 100,
) -> list[Auction]:
    auctions = (
        select(Auction)
        .options(*auction_load_options())
        .order_by(Auction.starts_at.desc(), Auction.created_at.desc(), Auction.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(auctions).all())


def get_user_auctions(
    db: Session,
    user_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[Auction]:
    auctions = (
        select(Auction)
        .options(*auction_load_options())
        .where(Auction.seller_id == user_id)
        .order_by(Auction.starts_at.desc(), Auction.created_at.desc(), Auction.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(auctions).all())


def get_auction(db: Session, auction_id: UUID) -> Auction | None:
    auction = (
        select(Auction).options(*auction_load_options()).where(Auction.id == auction_id)
    )
    return db.scalar(auction)


def get_auction_for_update(db: Session, auction_id: UUID) -> Auction | None:
    auction = select(Auction).where(Auction.id == auction_id).with_for_update()
    return db.scalar(auction)


def get_auction_lots_for_update(db: Session, auction_id: UUID) -> list[Lot]:
    lots = (
        select(Lot)
        .options(joinedload(Lot.item))
        .where(Lot.auction_id == auction_id)
        .order_by(Lot.lot_number)
        .with_for_update()
    )
    return list(db.scalars(lots).all())


def get_lot(db: Session, lot_id: UUID) -> Lot | None:
    lot = select(Lot).options(*lot_load_options()).where(Lot.id == lot_id)
    return db.scalar(lot)


def get_lot_for_update(db: Session, lot_id: UUID) -> Lot | None:
    lot = (
        select(Lot)
        .options(*lot_load_options())
        .where(Lot.id == lot_id)
        .with_for_update()
    )
    return db.scalar(lot)


def get_lot_bids(
    db: Session,
    lot_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[Bid]:
    bids = (
        select(Bid)
        .where(Bid.lot_id == lot_id)
        .order_by(Bid.created_at.desc(), Bid.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(bids).all())
