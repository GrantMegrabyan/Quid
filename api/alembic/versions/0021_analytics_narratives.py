"""analytics narratives

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_narratives",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("month", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.UniqueConstraint("month", name="uq_analytics_narratives_month"),
    )


def downgrade() -> None:
    op.drop_table("analytics_narratives")
