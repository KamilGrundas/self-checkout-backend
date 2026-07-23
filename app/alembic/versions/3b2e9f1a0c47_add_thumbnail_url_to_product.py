"""Add thumbnail_url to product

Revision ID: 3b2e9f1a0c47
Revises: 2f4b6a7c8d90
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '3b2e9f1a0c47'
down_revision = '2f4b6a7c8d90'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'product',
        sa.Column('thumbnail_url', sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('product', 'thumbnail_url')
