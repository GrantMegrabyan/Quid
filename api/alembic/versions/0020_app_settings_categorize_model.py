"""app settings categorize model

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "categorize_model",
            sa.String(),
            nullable=False,
            server_default="google/gemini-2.5-flash",
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "categorize_model")
