"""Add a per-integration inference read timeout.

Revision ID: b6c8d0e2f4a1
Revises: a4b7c9d2e1f0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6c8d0e2f4a1"
down_revision: str | None = "a4b7c9d2e1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "visioninferenceintegration",
        sa.Column("read_timeout_seconds", sa.Integer(), nullable=False, server_default="120"),
    )


def downgrade() -> None:
    op.drop_column("visioninferenceintegration", "read_timeout_seconds")
