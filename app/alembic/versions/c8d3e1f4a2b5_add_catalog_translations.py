"""Add catalog name translations and the application default language.

Revision ID: c8d3e1f4a2b5
Revises: b6c8d0e2f4a1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d3e1f4a2b5"
down_revision: str | None = "b6c8d0e2f4a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("category", sa.Column("name_en", sa.String(length=255), nullable=True))
    op.add_column("category", sa.Column("name_pl", sa.String(length=255), nullable=True))
    op.add_column("product", sa.Column("name_en", sa.String(length=255), nullable=True))
    op.add_column("product", sa.Column("name_pl", sa.String(length=255), nullable=True))
    op.execute("UPDATE category SET name_en = name WHERE name_en IS NULL")
    op.execute("UPDATE product SET name_en = name WHERE name_en IS NULL")
    op.create_table(
        "catalogsettings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "default_language",
            sa.Enum("en", "pl", name="cataloglanguage"),
            nullable=False,
            server_default="en",
        ),
        sa.CheckConstraint("id = 1", name="ck_catalogsettings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("catalogsettings")
    sa.Enum("en", "pl", name="cataloglanguage").drop(op.get_bind(), checkfirst=True)
    op.drop_column("product", "name_pl")
    op.drop_column("product", "name_en")
    op.drop_column("category", "name_pl")
    op.drop_column("category", "name_en")
