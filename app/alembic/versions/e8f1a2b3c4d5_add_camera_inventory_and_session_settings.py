"""Add checkout camera inventory and session settings snapshot.

Revision ID: e8f1a2b3c4d5
Revises: c4a6d8e0f2b1
Create Date: 2026-07-27 18:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1a2b3c4d5"
down_revision: str | None = "c4a6d8e0f2b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "checkoutcounter",
        sa.Column(
            "available_cameras",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "checkoutcounter",
        sa.Column(
            "available_cameras_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "checkoutsession",
        sa.Column(
            "counter_settings",
            sa.JSON(),
            server_default=sa.text(
                "json_build_object("
                "'ml_mode', 'off', "
                "'shelf_camera_device_id', NULL, "
                "'scale_camera_device_id', NULL, "
                "'language', 'pl'"
                ")"
            ),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE checkoutsession AS checkout_session
        SET counter_settings = json_build_object(
            'ml_mode', checkout_counter.ml_mode::text,
            'shelf_camera_device_id', checkout_counter.shelf_camera_device_id,
            'scale_camera_device_id', checkout_counter.scale_camera_device_id,
            'language', checkout_counter.language
        )
        FROM checkoutcounter AS checkout_counter
        WHERE checkout_counter.id = checkout_session.counter_id
        """
    )


def downgrade() -> None:
    op.drop_column("checkoutsession", "counter_settings")
    op.drop_column("checkoutcounter", "available_cameras_updated_at")
    op.drop_column("checkoutcounter", "available_cameras")
