"""expense importance_source provenance + importance correction log

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-23

Two changes, both in service of learning importance from the user's own
decisions.

``expenses.importance_source`` mirrors ``category_source``: it records WHERE a
transaction's importance came from, so a later automatic pass can overwrite a
guess without ever clobbering a hand-set value. Priority high->low:
``manual > rule > learned > ai > import``. ``learned`` is not written by
anything yet — it is in the CHECK from the start because widening a SQLite
CHECK means another full table rebuild, and ``expenses`` carries five of them.

Backfill: unlike ``category_source`` there is nothing to promote. Importance
has always defaulted to ``'important'`` with no provenance, so a stored value
cannot be attributed to the user, the AI, or the default — every existing row
is therefore left at ``'import'`` (fully overridable, and NOT a training
label). The triage queue is how that history gets labelled.

``importance_corrections`` is an append-only log of every time a human moved a
transaction's importance away from what was proposed. The expenses table only
ever holds the final answer; measuring whether suggestions are IMPROVING needs
the before/after pair, which is what this records. It deliberately carries no
foreign keys: the log's value is the (merchant, category, amount, chosen)
tuple, which must outlive the deletion of the expense or category it came from.
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import SAWarning

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMPORTANCE_VALUES = "'essential', 'important', 'discretionary'"
_SOURCE_VALUES = "'manual', 'rule', 'learned', 'ai', 'import'"
_CONTEXT_VALUES = "'edit', 'import_preview', 'triage'"


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column(
            "importance_source",
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
                "ck_expenses_importance_source",
                f"importance_source IN ({_SOURCE_VALUES})",
            )

    op.create_table(
        "importance_corrections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("expense_id", sa.String(), nullable=True),
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("merchant_name", sa.String(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("expense_date", sa.String(), nullable=False),
        sa.Column("from_importance", sa.String(), nullable=True),
        sa.Column("from_source", sa.String(), nullable=True),
        sa.Column("to_importance", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            f"from_importance IS NULL OR from_importance IN ({_IMPORTANCE_VALUES})",
            name="ck_importance_corrections_from",
        ),
        sa.CheckConstraint(
            f"to_importance IN ({_IMPORTANCE_VALUES})",
            name="ck_importance_corrections_to",
        ),
        sa.CheckConstraint(
            f"context IN ({_CONTEXT_VALUES})",
            name="ck_importance_corrections_context",
        ),
    )
    op.create_index(
        "ix_importance_corrections_merchant",
        "importance_corrections",
        ["merchant_key"],
    )
    op.create_index(
        "ix_importance_corrections_created",
        "importance_corrections",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_importance_corrections_created", table_name="importance_corrections")
    op.drop_index("ix_importance_corrections_merchant", table_name="importance_corrections")
    op.drop_table("importance_corrections")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("ck_expenses_importance_source", type_="check")
    op.drop_column("expenses", "importance_source")
