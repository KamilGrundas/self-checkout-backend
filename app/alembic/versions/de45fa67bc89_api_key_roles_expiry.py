"""Define the current API-key model for the pre-v0.1 application."""

import sqlalchemy as sa
from alembic import op

revision = "de45fa67bc89"
down_revision = "cd34ef56ab78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "apikey", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.add_column("apikey", sa.Column("role", sa.String(16), nullable=True))
    op.add_column("apikey", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column(
        "apikey",
        sa.Column("purpose", sa.String(32), nullable=False, server_default="generic"),
    )
    op.add_column("apikey", sa.Column("counter_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_apikey_owner", "apikey", "user", ["owner_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_apikey_counter",
        "apikey",
        "checkoutcounter",
        ["counter_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_apikey_active_checkout_counter",
        "apikey",
        ["counter_id"],
        unique=True,
        postgresql_where=sa.text("purpose = 'checkout_counter' AND revoked = false"),
    )
    op.alter_column("apikey", "purpose", server_default=None)


def downgrade() -> None:
    op.drop_index("uq_apikey_active_checkout_counter", table_name="apikey")
    op.drop_constraint("fk_apikey_counter", "apikey", type_="foreignkey")
    op.drop_column("apikey", "counter_id")
    op.drop_column("apikey", "purpose")
    op.drop_constraint("fk_apikey_owner", "apikey", type_="foreignkey")
    op.drop_column("apikey", "owner_id")
    op.drop_column("apikey", "role")
    op.alter_column(
        "apikey", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
