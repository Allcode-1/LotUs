from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func, ForeignKey, Enum as SAEnum, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.item_image import ItemImage


class ItemStatus(StrEnum):
    DRAFT = "draft"
    AVAILABLE = "available"
    IN_AUCTION = "in_auction"
    SOLD = "sold"
    ARCHIVED = "archived"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    title: Mapped[str] = mapped_column(String(55), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    creator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[ItemStatus] = mapped_column(
        SAEnum(
            ItemStatus,
            name="item_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ItemStatus.DRAFT,
    )

    images: Mapped[list["ItemImage"]] = relationship(
        "ItemImage",
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ItemImage.sort_order",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        server_default=func.now(),
        nullable=False,
    )
