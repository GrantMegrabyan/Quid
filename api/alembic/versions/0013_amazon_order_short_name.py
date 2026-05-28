"""amazon orders short_name

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "amazon_orders",
        sa.Column("short_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("amazon_orders", "short_name")
