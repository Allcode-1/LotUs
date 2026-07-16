from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.lot import Lot


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_bids_amount_positive"),)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    lot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bidder_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    lot: Mapped["Lot"] = relationship(
        "Lot",
        back_populates="bids",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
