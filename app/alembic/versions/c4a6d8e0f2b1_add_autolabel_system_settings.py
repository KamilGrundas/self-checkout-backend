"""Add autolabel system settings.

Revision ID: c4a6d8e0f2b1
Revises: b7e2c4d6f810
Create Date: 2026-07-27 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a6d8e0f2b1"
down_revision: str | None = "b7e2c4d6f810"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "autolabelsettings",
        sa.Column("endpoint_url", sa.String(length=2048), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="512"),
        sa.Column(
            "connect_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "read_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("id = 1", name="ck_autolabelsettings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("autolabelsettings")
