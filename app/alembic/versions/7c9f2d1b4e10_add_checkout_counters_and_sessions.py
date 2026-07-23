"""Add checkout counters and sessions

Revision ID: 7c9f2d1b4e10
Revises: 6d4b10ca58e7
Create Date: 2026-03-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7c9f2d1b4e10"
down_revision = "6d4b10ca58e7"
branch_labels = None
depends_on = None


checkout_session_payment_status = postgresql.ENUM(
    "pending",
    "paid",
    name="checkoutsessionpaymentstatus",
    create_type=False,
)


def upgrade():
    checkout_session_payment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "checkoutcounter",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "checkoutsession",
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("payment_status", checkout_session_payment_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cart", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["counter_id"], ["checkoutcounter.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("checkoutsession")
    op.drop_table("checkoutcounter")
    checkout_session_payment_status.drop(op.get_bind(), checkfirst=True)
