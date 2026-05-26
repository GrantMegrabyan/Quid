"""amazon orders + expense link

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-25
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import SAWarning

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "amazon_orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_date", sa.String(), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="GBP"),
        sa.Column("items_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("payment_last4", sa.String(), nullable=True),
        sa.Column("order_url", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("total > 0", name="ck_amazon_orders_total_positive"),
        sa.CheckConstraint(
            "order_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_amazon_orders_date_iso",
        ),
    )
    op.create_index("ix_amazon_orders_date", "amazon_orders", ["order_date"])
    op.create_index("ix_amazon_orders_total", "amazon_orders", ["total"])

    # Add nullable amazon_order_id FK on expenses. SQLite cannot add FK via
    # ALTER TABLE ADD COLUMN directly, so we use batch_alter_table to recreate.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.add_column(sa.Column("amazon_order_id", sa.String(), nullable=True))
            batch_op.create_foreign_key(
                "fk_expenses_amazon_order_id",
                "amazon_orders",
                ["amazon_order_id"],
                ["id"],
                ondelete="SET NULL",
            )
    op.create_index("ix_expenses_amazon_order", "expenses", ["amazon_order_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_amazon_order", table_name="expenses")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("fk_expenses_amazon_order_id", type_="foreignkey")
            batch_op.drop_column("amazon_order_id")
    op.drop_index("ix_amazon_orders_total", table_name="amazon_orders")
    op.drop_index("ix_amazon_orders_date", table_name="amazon_orders")
    op.drop_table("amazon_orders")
