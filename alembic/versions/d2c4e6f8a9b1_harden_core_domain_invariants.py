"""harden core domain invariants

Revision ID: d2c4e6f8a9b1
Revises: c6d4f3a8b9e2
Create Date: 2026-07-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2c4e6f8a9b1"
down_revision: Union[str, Sequence[str], None] = "c6d4f3a8b9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_lots_current_price_not_below_start",
        "lots",
        "current_price >= start_price",
    )
    op.create_check_constraint(
        "ck_lots_sale_confirmable_requires_last_bid",
        "lots",
        "sale_confirmable_at IS NULL OR last_bid_at IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_lots_sale_confirmable_after_last_bid",
        "lots",
        "sale_confirmable_at IS NULL OR sale_confirmable_at >= last_bid_at",
    )
    op.create_check_constraint(
        "ck_lots_sold_timestamp_price_pair",
        "lots",
        "(sold_at IS NULL AND sold_price IS NULL) "
        "OR (sold_at IS NOT NULL AND sold_price IS NOT NULL)",
    )
    op.create_index(
        "ix_lots_one_open_lot_per_item",
        "lots",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'active')"),
    )

    op.create_check_constraint(
        "ck_item_images_size_bytes_positive",
        "item_images",
        "size_bytes > 0",
    )
    op.create_check_constraint(
        "ck_item_images_sort_order_non_negative",
        "item_images",
        "sort_order >= 0",
    )
    op.create_unique_constraint(
        "uq_item_images_item_sort_order",
        "item_images",
        ["item_id", "sort_order"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_item_images_item_sort_order", "item_images")
    op.drop_constraint("ck_item_images_sort_order_non_negative", "item_images")
    op.drop_constraint("ck_item_images_size_bytes_positive", "item_images")

    op.drop_index("ix_lots_one_open_lot_per_item", table_name="lots")
    op.drop_constraint("ck_lots_sold_timestamp_price_pair", "lots")
    op.drop_constraint("ck_lots_sale_confirmable_after_last_bid", "lots")
    op.drop_constraint("ck_lots_sale_confirmable_requires_last_bid", "lots")
    op.drop_constraint("ck_lots_current_price_not_below_start", "lots")
