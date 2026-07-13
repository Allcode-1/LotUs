from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.auction import Auction
    from app.models.bid import Bid
    from app.models.item import Item


class LotStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SOLD = "sold"
    UNSOLD = "unsold"
    CANCELLED = "cancelled"


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("auction_id", "lot_number", name="uq_lots_auction_number"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    auction_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auctions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    lot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_bid_increment: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    winner_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_bid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sale_confirmable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sold_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[LotStatus] = mapped_column(
        SAEnum(
            LotStatus,
            name="lot_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=LotStatus.PENDING,
    )

    auction: Mapped["Auction"] = relationship(
        "Auction",
        back_populates="lots",
    )
    item: Mapped["Item"] = relationship(
        "Item",
        back_populates="lots",
    )
    bids: Mapped[list["Bid"]] = relationship(
        "Bid",
        back_populates="lot",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Bid.created_at.desc()",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
