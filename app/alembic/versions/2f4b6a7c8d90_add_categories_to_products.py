"""Add categories to products

Revision ID: 2f4b6a7c8d90
Revises: 7c9f2d1b4e10
Create Date: 2026-03-27 21:30:00.000000

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = "2f4b6a7c8d90"
down_revision = "7c9f2d1b4e10"
branch_labels = None
depends_on = None


DEFAULT_CATEGORY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if "category" not in inspector.get_table_names():
        op.create_table(
            "category",
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    category_indexes = {index["name"] for index in inspector.get_indexes("category")}
    index_name = op.f("ix_category_key")
    if index_name not in category_indexes:
        op.create_index(index_name, "category", ["key"], unique=True)

    op.execute(
        sa.text(
            """
            INSERT INTO category (id, name, key, created_at)
            VALUES (:id, 'Other', 'other', now())
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=DEFAULT_CATEGORY_ID)
    )

    product_columns = {column["name"] for column in inspector.get_columns("product")}
    if "category_id" not in product_columns:
        op.add_column(
            "product",
            sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    op.execute(
        sa.text("UPDATE product SET category_id = :id WHERE category_id IS NULL").bindparams(
            id=DEFAULT_CATEGORY_ID
        )
    )
    op.alter_column("product", "category_id", nullable=False)

    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("product")}
    if "product_category_id_fkey" not in foreign_keys:
        op.create_foreign_key(
            "product_category_id_fkey",
            "product",
            "category",
            ["category_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade():
    op.drop_constraint("product_category_id_fkey", "product", type_="foreignkey")
    op.drop_column("product", "category_id")
    op.drop_index(op.f("ix_category_key"), table_name="category")
    op.drop_table("category")
