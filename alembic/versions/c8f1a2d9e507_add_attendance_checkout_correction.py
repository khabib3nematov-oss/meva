"""add attendance checkout correction metadata

Revision ID: c8f1a2d9e507
Revises: b7d3f4a1c902
Create Date: 2026-09-27

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c8f1a2d9e507"
down_revision: str | None = "b7d3f4a1c902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendances",
        sa.Column("check_out_corrected_by_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "attendances",
        sa.Column("check_out_corrected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "attendances",
        sa.Column("check_out_correction_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attendances", "check_out_correction_reason")
    op.drop_column("attendances", "check_out_corrected_at")
    op.drop_column("attendances", "check_out_corrected_by_telegram_id")