from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.auction import AuctionStatus
from app.models.lot import LotStatus
from app.schemas.item import ItemRead


class AuctionLotCreate(BaseModel):
    item_id: UUID
    start_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    min_bid_increment: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )


class AuctionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    starts_at: datetime
    ends_at: datetime
    min_bid_increment: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    lots: list[AuctionLotCreate] = Field(min_length=1, max_length=50)


class BidCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class BidRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lot_id: UUID
    bidder_id: UUID
    amount: Decimal
    created_at: datetime


class LotRead(BaseModel):
    id: UUID
    auction_id: UUID
    item_id: UUID
    lot_number: int
    start_price: Decimal
    min_bid_increment: Decimal | None
    current_price: Decimal
    winner_id: UUID | None
    last_bid_at: datetime | None
    sale_confirmable_at: datetime | None
    sold_price: Decimal | None
    sold_at: datetime | None
    status: LotStatus
    created_at: datetime
    updated_at: datetime
    item: ItemRead


class AuctionRead(BaseModel):
    id: UUID
    seller_id: UUID
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    min_bid_increment: Decimal
    status: AuctionStatus
    created_at: datetime
    updated_at: datetime
    lots: list[LotRead]
