"""amazon order ↔ expense many-to-many link table

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-28

A single bank charge can cover several Amazon orders that were billed
together. Move from the 1:1 ``expenses.amazon_order_id`` FK to a join
table so we can record that relationship correctly.
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import SAWarning

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expense_amazon_orders",
        sa.Column("expense_id", sa.String(), nullable=False),
        sa.Column("amazon_order_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["amazon_order_id"],
            ["amazon_orders.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("expense_id", "amazon_order_id"),
    )
    op.create_index(
        "ix_expense_amazon_orders_amazon_order_id",
        "expense_amazon_orders",
        ["amazon_order_id"],
    )

    # Backfill from the legacy 1:1 column before dropping it.
    op.execute(
        "INSERT INTO expense_amazon_orders (expense_id, amazon_order_id) "
        "SELECT id, amazon_order_id FROM expenses "
        "WHERE amazon_order_id IS NOT NULL"
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_index("ix_expenses_amazon_order")
            batch_op.drop_constraint(
                "fk_expenses_amazon_order_id", type_="foreignkey"
            )
            batch_op.drop_column("amazon_order_id")


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.add_column(
                sa.Column("amazon_order_id", sa.String(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_expenses_amazon_order_id",
                "amazon_orders",
                ["amazon_order_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_expenses_amazon_order", ["amazon_order_id"]
            )

    # Restore one link per expense (lexically lowest order id wins) — this is
    # a lossy downgrade but preserves a deterministic primary link.
    op.execute(
        "UPDATE expenses SET amazon_order_id = ("
        "  SELECT MIN(amazon_order_id) FROM expense_amazon_orders "
        "  WHERE expense_amazon_orders.expense_id = expenses.id"
        ")"
    )

    op.drop_index(
        "ix_expense_amazon_orders_amazon_order_id",
        table_name="expense_amazon_orders",
    )
    op.drop_table("expense_amazon_orders")
