"""add item images storage

Revision ID: a64c9c7f9a21
Revises: 79513486657f
Create Date: 2026-07-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a64c9c7f9a21"
down_revision: Union[str, Sequence[str], None] = "79513486657f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


item_status = postgresql.ENUM(
    "draft",
    "available",
    "in_auction",
    "sold",
    "archived",
    name="item_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE item_status AS ENUM (
                'draft',
                'available',
                'in_auction',
                'sold',
                'archived'
            );
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )

    op.drop_table("items")

    op.create_table(
        "items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=55), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            item_status,
            nullable=False,
            server_default="draft",
        ),
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
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_items_creator_id"), "items", ["creator_id"], unique=False)
    op.create_index(op.f("ix_items_owner_id"), "items", ["owner_id"], unique=False)

    op.create_table(
        "item_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_item_images_item_id"), "item_images", ["item_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_item_images_item_id"), table_name="item_images")
    op.drop_table("item_images")
    op.drop_index(op.f("ix_items_owner_id"), table_name="items")
    op.drop_index(op.f("ix_items_creator_id"), table_name="items")
    op.drop_table("items")

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=55), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )

    bind = op.get_bind()
    item_status.drop(bind, checkfirst=True)
