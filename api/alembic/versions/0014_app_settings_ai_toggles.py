"""app settings AI toggles

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "ai_categorize_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "ai_short_names_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "ai_short_names_enabled")
    op.drop_column("app_settings", "ai_categorize_enabled")
