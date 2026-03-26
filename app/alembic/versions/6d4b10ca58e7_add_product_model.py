"""Add product model

Revision ID: 6d4b10ca58e7
Revises: fe56fa70289e
Create Date: 2026-03-26 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "6d4b10ca58e7"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


product_unit = postgresql.ENUM("kg", "pcs", name="productunit", create_type=False)


def upgrade():
    product_unit.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "product",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit", product_unit, nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("product")
    product_unit.drop(op.get_bind(), checkfirst=True)
