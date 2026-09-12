"""Remove obsolete external identity columns."""

import sqlalchemy as sa
from alembic import op

revision = "ef67ab89cd01"
down_revision = "de45fa67bc89"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_user_oidc_identity", "user", type_="unique")
    op.drop_column("user", "oidc_subject")
    op.drop_column("user", "oidc_issuer")


def downgrade() -> None:
    op.add_column("user", sa.Column("oidc_issuer", sa.String(2048), nullable=True))
    op.add_column("user", sa.Column("oidc_subject", sa.String(255), nullable=True))
    op.create_unique_constraint(
        "uq_user_oidc_identity", "user", ["oidc_issuer", "oidc_subject"]
    )
