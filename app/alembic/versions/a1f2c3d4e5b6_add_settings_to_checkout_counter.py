"""Add settings columns to checkout counter

Revision ID: a1f2c3d4e5b6
Revises: 1a31ce608336
Create Date: 2026-04-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a1f2c3d4e5b6"
down_revision = ("3b2e9f1a0c47", "7c9f2d1b4e10")
branch_labels = None
depends_on = None


checkout_ml_mode = postgresql.ENUM(
    "off",
    "label",
    "on",
    name="checkoutmlmode",
    create_type=False,
)


def upgrade():
    checkout_ml_mode.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "checkoutcounter",
        sa.Column(
            "ml_mode",
            checkout_ml_mode,
            nullable=False,
            server_default="off",
        ),
    )
    op.add_column(
        "checkoutcounter",
        sa.Column("shelf_camera_device_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "checkoutcounter",
        sa.Column("scale_camera_device_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "checkoutcounter",
        sa.Column(
            "language",
            sa.String(length=8),
            nullable=False,
            server_default="pl",
        ),
    )


def downgrade():
    op.drop_column("checkoutcounter", "language")
    op.drop_column("checkoutcounter", "scale_camera_device_id")
    op.drop_column("checkoutcounter", "shelf_camera_device_id")
    op.drop_column("checkoutcounter", "ml_mode")
    checkout_ml_mode.drop(op.get_bind(), checkfirst=True)
