"""Add explicit OIDC identities and revocable scoped API keys."""

from alembic import op
import sqlalchemy as sa

revision = "ab12cd34ef56"
down_revision = "f3a1c5e7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("oidc_issuer", sa.String(2048), nullable=True))
    op.add_column("user", sa.Column("oidc_subject", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_user_oidc_identity", "user", ["oidc_issuer", "oidc_subject"])
    op.create_table(
        "apikey",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_apikey_key_hash", "apikey", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("apikey")
    op.drop_constraint("uq_user_oidc_identity", "user", type_="unique")
    op.drop_column("user", "oidc_subject")
    op.drop_column("user", "oidc_issuer")
