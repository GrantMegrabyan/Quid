"""import rule set_importance

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-22

Adds the third rule setter, alongside ``set_display_name`` and ``set_note``.
Like those two it is a plain nullable column with no table CHECK: adding one to
SQLite means a full table rebuild, and ``import_rules`` carries a dozen CHECK
constraints that a batch rebuild would have to reproduce exactly. The value is
constrained at the two layers that already guard the other setters — the
Pydantic ``Importance`` literal at the API boundary, and
``ImportRuleRepository._validate`` before any write.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_rules",
        sa.Column("set_importance", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_rules", "set_importance")
