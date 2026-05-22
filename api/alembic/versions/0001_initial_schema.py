"""initial schema with uncategorized seed row

Revision ID: 0001
Revises:
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_categories_name_ci "
        "ON categories (lower(trim(name)))"
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint(
            "date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_expenses_date_iso",
        ),
    )
    op.create_index("ix_expenses_date", "expenses", ["date"])
    op.create_index("ix_expenses_category", "expenses", ["category_id"])

    op.execute(
        "INSERT INTO categories (id, name, color, icon) "
        "VALUES ('uncategorized', 'Uncategorized', '#9CA3AF', 'circle-help')"
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_category", table_name="expenses")
    op.drop_index("ix_expenses_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_categories_name_ci", table_name="categories")
    op.drop_table("categories")
