from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.item import Item


class ItemImage(Base):
    __tablename__ = "item_images"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_item_images_size_bytes_positive"),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_item_images_sort_order_non_negative",
        ),
        UniqueConstraint(
            "item_id",
            "sort_order",
            name="uq_item_images_item_sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item: Mapped[Item] = relationship(
        "Item",
        back_populates="images",
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
