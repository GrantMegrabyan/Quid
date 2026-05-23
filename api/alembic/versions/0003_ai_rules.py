"""ai rules

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(trim(text)) > 0", name="ck_ai_rules_text_not_blank"),
    )
    op.create_index("ix_ai_rules_priority", "ai_rules", ["priority"])
    op.execute(
        "INSERT INTO ai_rules (id, text, enabled, priority, created_at) VALUES "
        "('ai-rule-exclude-transfers', 'Exclude transfers from categorisation/imports.', 1, 0, '2026-05-23T00:00:00Z'), "
        "('ai-rule-exclude-refunds', 'If a purchase is fully refunded, exclude both the original purchase and the refund.', 1, 10, '2026-05-23T00:00:00Z')"
    )


def downgrade() -> None:
    op.drop_index("ix_ai_rules_priority", table_name="ai_rules")
    op.drop_table("ai_rules")
