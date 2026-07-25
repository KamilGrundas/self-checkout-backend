"""Add encrypted Label Studio API key to user.

Revision ID: b7e2c4d6f810
Revises: a1f2c3d4e5b6
Create Date: 2026-07-24 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2c4d6f810"
down_revision: str | None = "a1f2c3d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("label_studio_api_key_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "label_studio_api_key_encrypted")
