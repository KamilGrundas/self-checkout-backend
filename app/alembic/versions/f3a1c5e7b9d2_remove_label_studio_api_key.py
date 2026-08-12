"""Remove obsolete Label Studio credentials.

Revision ID: f3a1c5e7b9d2
Revises: e8f1a2b3c4d5
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

revision = "f3a1c5e7b9d2"
down_revision = "e8f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("user", "label_studio_api_key_encrypted")


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column("label_studio_api_key_encrypted", sa.Text(), nullable=True),
    )
