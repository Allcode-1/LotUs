"""add idempotency records

Revision ID: e5b8d2a7c9f4
Revises: d2c4e6f8a9b1
Create Date: 2026-07-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b8d2a7c9f4"
down_revision: Union[str, Sequence[str], None] = "d2c4e6f8a9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('processing', 'completed')",
            name="ck_idempotency_records_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "operation",
            "key",
            name="uq_idempotency_records_user_operation_key",
        ),
    )
    op.create_index(
        "ix_idempotency_records_expires_at",
        "idempotency_records",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_idempotency_records_user_id"),
        "idempotency_records",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_idempotency_records_user_id"), table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
