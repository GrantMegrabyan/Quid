"""import log

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("imported_at", sa.String(), nullable=False),
        sa.Column("files", sa.Text(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_excluded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_logs_imported_at", "import_logs", ["imported_at"])


def downgrade() -> None:
    op.drop_index("ix_import_logs_imported_at", table_name="import_logs")
    op.drop_table("import_logs")
