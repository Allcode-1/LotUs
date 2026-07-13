"""add lot sale timestamps

Revision ID: c6d4f3a8b9e2
Revises: b7f8c2d9e4a1
Create Date: 2026-07-13 00:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6d4f3a8b9e2"
down_revision: Union[str, Sequence[str], None] = "b7f8c2d9e4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "lots",
        sa.Column("last_bid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lots",
        sa.Column("sale_confirmable_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lots",
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lots", "sold_at")
    op.drop_column("lots", "sale_confirmable_at")
    op.drop_column("lots", "last_bid_at")
