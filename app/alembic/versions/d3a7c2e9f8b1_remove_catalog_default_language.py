"""Remove the catalog-wide default language setting.

Revision ID: d3a7c2e9f8b1
Revises: c8d3e1f4a2b5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3a7c2e9f8b1"
down_revision: str | None = "c8d3e1f4a2b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("catalogsettings")
    sa.Enum("en", "pl", name="cataloglanguage").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    catalog_language = sa.Enum("en", "pl", name="cataloglanguage")
    catalog_language.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "catalogsettings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "default_language",
            catalog_language,
            nullable=False,
            server_default="en",
        ),
        sa.CheckConstraint("id = 1", name="ck_catalogsettings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
