from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Balance(Base):
    __tablename__ = "balance"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_balance_amount_non_negative"),
        CheckConstraint(
            "reserved_amount >= 0",
            name="ck_balance_reserved_amount_non_negative",
        ),
        CheckConstraint(
            "reserved_amount <= amount",
            name="ck_balance_reserved_not_greater_amount",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    reserved_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    @property
    def available_amount(self) -> Decimal:
        return self.amount - self.reserved_amount
