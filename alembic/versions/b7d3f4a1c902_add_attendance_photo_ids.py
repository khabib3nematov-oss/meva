"""add attendance photo ids

Revision ID: b7d3f4a1c902
Revises: 94476acce711
Create Date: 2026-09-18

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7d3f4a1c902"
down_revision: str | None = "94476acce711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendances",
        sa.Column("check_in_photo_file_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "attendances",
        sa.Column("check_out_photo_file_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attendances", "check_out_photo_file_id")
    op.drop_column("attendances", "check_in_photo_file_id")