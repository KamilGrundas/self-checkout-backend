"""Add owner-bound API roles and optional expiration without broadening legacy keys."""

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
    op.create_foreign_key(
        "fk_apikey_owner", "apikey", "user", ["owner_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    # An older schema cannot represent unlimited credentials; expire those keys.
    op.execute(
        "UPDATE apikey SET expires_at = CURRENT_TIMESTAMP, revoked = true WHERE expires_at IS NULL"
    )
    # Role keys have no legacy scopes and must not silently acquire any.
    op.execute("UPDATE apikey SET revoked = true WHERE role IS NOT NULL")
    op.drop_constraint("fk_apikey_owner", "apikey", type_="foreignkey")
    op.drop_column("apikey", "owner_id")
    op.drop_column("apikey", "role")
    op.alter_column(
        "apikey", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
