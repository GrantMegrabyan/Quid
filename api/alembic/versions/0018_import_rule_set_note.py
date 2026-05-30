"""import rule set_note

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_rules",
        sa.Column("set_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_rules", "set_note")
