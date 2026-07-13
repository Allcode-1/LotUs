"""add auctions lots bids

Revision ID: b7f8c2d9e4a1
Revises: a64c9c7f9a21
Create Date: 2026-07-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7f8c2d9e4a1"
down_revision: Union[str, Sequence[str], None] = "a64c9c7f9a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


auction_status = postgresql.ENUM(
    "scheduled",
    "active",
    "finished",
    "cancelled",
    name="auction_status",
    create_type=False,
)
lot_status = postgresql.ENUM(
    "pending",
    "active",
    "sold",
    "unsold",
    "cancelled",
    name="lot_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE auction_status AS ENUM (
                'scheduled',
                'active',
                'finished',
                'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE lot_status AS ENUM (
                'pending',
                'active',
                'sold',
                'unsold',
                'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )

    op.add_column(
        "balance",
        sa.Column(
            "reserved_amount",
            sa.Numeric(12, 2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_balance_amount_non_negative",
        "balance",
        "amount >= 0",
    )
    op.create_check_constraint(
        "ck_balance_reserved_amount_non_negative",
        "balance",
        "reserved_amount >= 0",
    )
    op.create_check_constraint(
        "ck_balance_reserved_not_greater_amount",
        "balance",
        "reserved_amount <= amount",
    )

    op.create_table(
        "auctions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("min_bid_increment", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", auction_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_auctions_time_window"),
        sa.CheckConstraint(
            "min_bid_increment > 0",
            name="ck_auctions_min_bid_increment_positive",
        ),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auctions_seller_id"), "auctions", ["seller_id"])

    op.create_table(
        "lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("auction_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("lot_number", sa.Integer(), nullable=False),
        sa.Column("start_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_bid_increment", sa.Numeric(12, 2), nullable=True),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("winner_id", sa.Uuid(), nullable=True),
        sa.Column("sold_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", lot_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("lot_number > 0", name="ck_lots_lot_number_positive"),
        sa.CheckConstraint("start_price > 0", name="ck_lots_start_price_positive"),
        sa.CheckConstraint("current_price > 0", name="ck_lots_current_price_positive"),
        sa.CheckConstraint(
            "min_bid_increment IS NULL OR min_bid_increment > 0",
            name="ck_lots_min_bid_increment_positive",
        ),
        sa.CheckConstraint(
            "sold_price IS NULL OR sold_price > 0",
            name="ck_lots_sold_price_positive",
        ),
        sa.ForeignKeyConstraint(["auction_id"], ["auctions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auction_id", "lot_number", name="uq_lots_auction_number"),
    )
    op.create_index(op.f("ix_lots_auction_id"), "lots", ["auction_id"])
    op.create_index(op.f("ix_lots_item_id"), "lots", ["item_id"])
    op.create_index(op.f("ix_lots_winner_id"), "lots", ["winner_id"])

    op.create_table(
        "bids",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_bids_amount_positive"),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bidder_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bids_lot_id"), "bids", ["lot_id"])
    op.create_index(op.f("ix_bids_bidder_id"), "bids", ["bidder_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_bids_bidder_id"), table_name="bids")
    op.drop_index(op.f("ix_bids_lot_id"), table_name="bids")
    op.drop_table("bids")

    op.drop_index(op.f("ix_lots_winner_id"), table_name="lots")
    op.drop_index(op.f("ix_lots_item_id"), table_name="lots")
    op.drop_index(op.f("ix_lots_auction_id"), table_name="lots")
    op.drop_table("lots")

    op.drop_index(op.f("ix_auctions_seller_id"), table_name="auctions")
    op.drop_table("auctions")

    op.drop_constraint("ck_balance_reserved_not_greater_amount", "balance")
    op.drop_constraint("ck_balance_reserved_amount_non_negative", "balance")
    op.drop_constraint("ck_balance_amount_non_negative", "balance")
    op.drop_column("balance", "reserved_amount")

    bind = op.get_bind()
    lot_status.drop(bind, checkfirst=True)
    auction_status.drop(bind, checkfirst=True)
