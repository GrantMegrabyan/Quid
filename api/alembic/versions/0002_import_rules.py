"""import rules

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_category_id", sa.String(), nullable=True),
        sa.Column("match_name_op", sa.String(), nullable=True),
        sa.Column("match_name_value", sa.String(), nullable=True),
        sa.Column("match_amount_op", sa.String(), nullable=True),
        sa.Column("match_amount_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("match_amount_value2", sa.Numeric(12, 2), nullable=True),
        sa.Column("match_date_from", sa.String(), nullable=True),
        sa.Column("match_date_to", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["target_category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("action IN ('exclude', 'categorize')", name="ck_import_rules_action"),
        sa.CheckConstraint(
            "(action = 'exclude' AND target_category_id IS NULL) "
            "OR (action = 'categorize' AND target_category_id IS NOT NULL)",
            name="ck_import_rules_action_target",
        ),
        sa.CheckConstraint(
            "(match_name_op IS NULL) = (match_name_value IS NULL)",
            name="ck_import_rules_name_pair",
        ),
        sa.CheckConstraint(
            "match_name_op IS NULL OR match_name_op IN "
            "('contains', 'equals', 'starts_with', 'ends_with')",
            name="ck_import_rules_name_op",
        ),
        sa.CheckConstraint(
            "(match_amount_op IS NULL) = (match_amount_value IS NULL)",
            name="ck_import_rules_amount_pair",
        ),
        sa.CheckConstraint(
            "match_amount_op IS NULL OR match_amount_op IN ('gte', 'lte', 'eq', 'between')",
            name="ck_import_rules_amount_op",
        ),
        sa.CheckConstraint(
            "(match_amount_op = 'between') = (match_amount_value2 IS NOT NULL)",
            name="ck_import_rules_amount_v2",
        ),
        sa.CheckConstraint(
            "match_date_from IS NULL OR "
            "match_date_from GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_import_rules_date_from_iso",
        ),
        sa.CheckConstraint(
            "match_date_to IS NULL OR "
            "match_date_to GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_import_rules_date_to_iso",
        ),
        sa.CheckConstraint(
            "match_name_op IS NOT NULL OR match_amount_op IS NOT NULL OR "
            "match_date_from IS NOT NULL OR match_date_to IS NOT NULL",
            name="ck_import_rules_has_match",
        ),
    )
    op.create_index("ix_import_rules_priority", "import_rules", ["priority"])
    op.execute(
        "INSERT INTO import_rules "
        "(id, name, enabled, priority, action, target_category_id, "
        "match_name_op, match_name_value, created_at) "
        "VALUES "
        "('rule-exclude-transfers', 'Exclude transfers', 1, 0, 'exclude', NULL, "
        "'contains', 'transfer', '2026-05-23T00:00:00Z')"
    )


def downgrade() -> None:
    op.drop_index("ix_import_rules_priority", table_name="import_rules")
    op.drop_table("import_rules")
