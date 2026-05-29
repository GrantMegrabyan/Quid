"""expense category_source provenance

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-29

Adds ``expenses.category_source`` recording where an expense's category came
from, so an Amazon order's (more precise) category can override a generic
guess but never a hand-set one. Priority high->low:
``manual > rule > amazon > ai > import``.

Backfill of existing rows:
- column server_default ``'import'`` marks every existing row overridable;
- rows that are NOT uncategorized are then promoted to ``'manual'`` so any
  hand-set specific category is protected from future Amazon overrides;
- Amazon-linked rows whose category is the coarse "Shopping" bucket are
  demoted back to ``'ai'`` so the backfill command can re-categorise them
  with the precise per-order category (the whole point of this change).
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import SAWarning

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column(
            "category_source",
            sa.String(),
            nullable=False,
            server_default="import",
        ),
    )
    # SQLite cannot add a CHECK via ALTER; recreate the table via batch. The
    # rebuild reflects categories' expression-based index, which emits a benign
    # SAWarning that pytest's strict policy would otherwise raise.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.create_check_constraint(
                "ck_expenses_category_source",
                "category_source IN ('manual', 'rule', 'amazon', 'ai', 'import')",
            )

    # Protect existing hand-set categories: anything already categorised to a
    # specific (non-uncategorized) category is treated as 'manual'.
    op.execute(
        "UPDATE expenses SET category_source = 'manual' WHERE category_id <> 'uncategorized'"
    )

    # Re-expose the coarse "Shopping" bucket on Amazon-linked expenses as 'ai'
    # so the Amazon backfill can replace it with the precise order category.
    # Match Shopping by name (survives a renamed/recreated category id).
    op.execute(
        "UPDATE expenses SET category_source = 'ai' "
        "WHERE id IN (SELECT expense_id FROM expense_amazon_orders) "
        "AND category_id IN ("
        "  SELECT id FROM categories WHERE lower(trim(name)) = 'shopping'"
        ")"
    )


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("ck_expenses_category_source", type_="check")
    op.drop_column("expenses", "category_source")
