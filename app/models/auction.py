from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.lot import Lot


class AuctionStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class Auction(Base):
    __tablename__ = "auctions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_auctions_time_window"),
        CheckConstraint(
            "min_bid_increment > 0",
            name="ck_auctions_min_bid_increment_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    seller_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    min_bid_increment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[AuctionStatus] = mapped_column(
        SAEnum(
            AuctionStatus,
            name="auction_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AuctionStatus.SCHEDULED,
    )

    lots: Mapped[list["Lot"]] = relationship(
        "Lot",
        back_populates="auction",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Lot.lot_number",
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
