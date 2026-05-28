"""import rule match_day_of_month

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-28
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import SAWarning

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite cannot DROP/ADD a CHECK constraint via ALTER TABLE, so use
    # batch_alter_table to recreate the table with the updated has_match
    # constraint and the new day_of_month constraint. batch_alter_table reflects
    # FK-related tables (categories) which carry an expression-based index that
    # SQLAlchemy cannot model; suppress that benign warning here.
    op.add_column(
        "import_rules",
        sa.Column("match_day_of_month", sa.Integer(), nullable=True),
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("import_rules") as batch_op:
            batch_op.drop_constraint("ck_import_rules_has_match", type_="check")
            batch_op.create_check_constraint(
                "ck_import_rules_has_match",
                "match_name_op IS NOT NULL OR match_amount_op IS NOT NULL "
                "OR match_date_from IS NOT NULL OR match_date_to IS NOT NULL "
                "OR match_day_of_month IS NOT NULL",
            )
            batch_op.create_check_constraint(
                "ck_import_rules_day_of_month",
                "match_day_of_month IS NULL OR "
                "(match_day_of_month >= 1 AND match_day_of_month <= 31)",
            )


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("import_rules") as batch_op:
            batch_op.drop_constraint("ck_import_rules_day_of_month", type_="check")
            batch_op.drop_constraint("ck_import_rules_has_match", type_="check")
            batch_op.create_check_constraint(
                "ck_import_rules_has_match",
                "match_name_op IS NOT NULL OR match_amount_op IS NOT NULL OR "
                "match_date_from IS NOT NULL OR match_date_to IS NOT NULL",
            )
    op.drop_column("import_rules", "match_day_of_month")
