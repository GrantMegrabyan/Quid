"""import log source + raw_input for AI free-form imports

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-29

Adds two columns to ``import_logs`` so the import history can record how a
batch of transactions entered the system:

- ``source`` ('csv' | 'freeform'); existing rows default to 'csv'.
- ``raw_input`` (nullable): the exact free-form text the user submitted to the
  AI free-form import, kept so they can see what was parsed. NULL for CSV.
"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import SAWarning

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_logs",
        sa.Column(
            "source",
            sa.String(),
            nullable=False,
            server_default="csv",
        ),
    )
    op.add_column(
        "import_logs",
        sa.Column("raw_input", sa.Text(), nullable=True),
    )
    # SQLite cannot add a CHECK via ALTER; recreate the table via batch. The
    # rebuild may reflect expression-based indexes elsewhere, which emits a
    # benign SAWarning that pytest's strict policy would otherwise raise.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("import_logs") as batch_op:
            batch_op.create_check_constraint(
                "ck_import_logs_source",
                "source IN ('csv', 'freeform')",
            )


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("import_logs") as batch_op:
            batch_op.drop_constraint("ck_import_logs_source", type_="check")
    op.drop_column("import_logs", "raw_input")
    op.drop_column("import_logs", "source")
