"""Add OpenAI-compatible autolabel model and encrypted credential."""

import sqlalchemy as sa
from alembic import op

revision = "cd34ef56ab78"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "autolabelsettings",
        sa.Column("model_name", sa.String(512), nullable=False, server_default=""),
    )
    op.add_column(
        "autolabelsettings", sa.Column("api_key_encrypted", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("autolabelsettings", "api_key_encrypted")
    op.drop_column("autolabelsettings", "model_name")
