"""expense importance

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-25
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import SAWarning

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _alter_expenses() -> None:
    # SQLite cannot add a CHECK constraint via ALTER TABLE ADD COLUMN; add the
    # column with a default first, then recreate the table via batch_alter_table
    # to install the CHECK constraint. batch_alter_table reflects FK-related
    # tables (categories) which carry an expression-based index that SQLAlchemy
    # cannot model; suppress that benign reflection warning here so it does not
    # surface during pytest's strict warning policy.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.create_check_constraint(
                "ck_expenses_importance",
                "importance IN ('essential', 'important', 'discretionary')",
            )


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column(
            "importance",
            sa.String(),
            nullable=False,
            server_default="important",
        ),
    )
    _alter_expenses()


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("ck_expenses_importance", type_="check")
    op.drop_column("expenses", "importance")
