"""app settings singleton

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="GBP"),
        sa.Column(
            "show_importance_badge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 'singleton'", name="ck_app_settings_singleton"),
        sa.CheckConstraint(
            "length(trim(currency)) = 3",
            name="ck_app_settings_currency_len",
        ),
    )
    op.execute(
        "INSERT INTO app_settings (id, currency, show_importance_badge, updated_at) "
        "VALUES ('singleton', 'GBP', 1, '2026-05-25T00:00:00Z')"
    )


def downgrade() -> None:
    op.drop_table("app_settings")
