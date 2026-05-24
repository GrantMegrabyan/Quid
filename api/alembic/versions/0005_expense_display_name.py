"""expense display_name

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("display_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "import_rules",
        sa.Column("set_display_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("expenses", "display_name")
    op.drop_column("import_rules", "set_display_name")
