"""add user registration approval workflow

Revision ID: f2c9a6e1b403
Revises: c8f1a2d9e507
Create Date: 2026-09-27

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2c9a6e1b403"
down_revision: str | None = "c8f1a2d9e507"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default=sa.text("'APPROVED'"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("approval_decided_by_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "approval_decided_at")
    op.drop_column("users", "approval_decided_by_telegram_id")
    op.drop_column("users", "approval_status")