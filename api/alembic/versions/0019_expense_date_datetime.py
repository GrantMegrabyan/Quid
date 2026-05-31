"""widen expense date CHECK to allow an optional time component

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-31

Expenses now store either a bare ``YYYY-MM-DD`` date OR a full
``YYYY-MM-DDTHH:MM:SS`` local timestamp. The time lets two same-day,
same-merchant, same-amount transactions be distinguished during import dedupe
(see ``repositories/expenses.py::bulk_import``).

This migration only widens the ``ck_expenses_date_iso`` CHECK constraint to
accept the optional time part. Existing rows are ``YYYY-MM-DD`` and stay valid
under the widened constraint — there is intentionally NO backfill (we do not
fabricate a midnight that never happened; lexical sort and day-prefix grouping
already treat date-only rows correctly).

SQLite cannot alter a named CHECK in place, so the table is recreated via
``batch_alter_table`` (drop old constraint, create the widened one).
"""

import warnings
from collections.abc import Sequence

from alembic import op
from sqlalchemy.exc import SAWarning

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CHECK = "date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
_NEW_CHECK = (
    "date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
    "OR date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
    "T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
)


def upgrade() -> None:
    # The rebuild reflects categories' expression-based index, which emits a
    # benign SAWarning that pytest's strict policy would otherwise raise.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("ck_expenses_date_iso", type_="check")
            batch_op.create_check_constraint("ck_expenses_date_iso", _NEW_CHECK)


def downgrade() -> None:
    # Downgrade is best-effort: any rows that carry a time component would
    # violate the narrowed CHECK, so strip the time back to a bare date first.
    op.execute("UPDATE expenses SET date = substr(date, 1, 10) WHERE date LIKE '%T%'")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("ck_expenses_date_iso", type_="check")
            batch_op.create_check_constraint("ck_expenses_date_iso", _OLD_CHECK)
