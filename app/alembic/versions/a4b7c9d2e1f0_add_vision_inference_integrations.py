"""Replace the singleton vision provider with named integrations.

Revision ID: a4b7c9d2e1f0
Revises: ef67ab89cd01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4b7c9d2e1f0"
down_revision: str | None = "ef67ab89cd01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visioninferenceintegration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("endpoint_url", sa.String(2048), nullable=False),
        sa.Column("model_name", sa.String(512), nullable=True),
        sa.Column("api_key_encrypted", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "autolabelsettings", sa.Column("active_integration_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_autolabelsettings_active_integration_id",
        "autolabelsettings",
        ["active_integration_id"],
    )
    op.execute(
        """
        WITH source AS (
          SELECT id, endpoint_url, model_name, api_key_encrypted, updated_at,
                 uuid_generate_v4() AS integration_id
          FROM autolabelsettings
          WHERE endpoint_url IS NOT NULL
        ), inserted AS (
          INSERT INTO visioninferenceintegration
            (id, name, endpoint_url, model_name, api_key_encrypted, active, created_at, updated_at)
          SELECT integration_id, 'Migrated vision inference provider', endpoint_url,
                 NULLIF(model_name, ''), api_key_encrypted,
                 model_name <> '' AND api_key_encrypted IS NOT NULL,
                 updated_at, updated_at
          FROM source
          RETURNING id
        )
        UPDATE autolabelsettings AS settings
        SET active_integration_id = source.integration_id
        FROM source
        WHERE settings.id = source.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_autolabelsettings_active_integration_id", table_name="autolabelsettings")
    op.drop_column("autolabelsettings", "active_integration_id")
    op.drop_table("visioninferenceintegration")
