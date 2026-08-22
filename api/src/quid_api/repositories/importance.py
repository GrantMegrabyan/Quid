"""Importance provenance: the correction log and the merchant triage queue.

Importance is the one classification quid asks the user to own. To ever learn
it, two things have to be true that were not before:

1. every stored importance carries a ``importance_source`` saying who chose it,
   so a hand-set value is distinguishable from the ``'important'`` default;
2. every time a human moves an importance away from what was proposed, the
   before/after pair is recorded — the expenses table only keeps the final
   answer, which cannot tell you whether suggestions are improving.

The triage queue is the bootstrap for (1): with no manual labels, history is
entirely unattributed, so this ranks the merchants where a single decision
buys the most labelled spend and lets the user work down the list.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import case, func, select

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Expense, ImportanceCorrection

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement


VALID_IMPORTANCE: frozenset[str] = frozenset({"essential", "important", "discretionary"})
VALID_SOURCE: frozenset[str] = frozenset({"manual", "rule", "learned", "ai", "import"})
VALID_CONTEXT: frozenset[str] = frozenset({"edit", "import_preview", "triage"})

_WS_RE = re.compile(r"\s+")


def merchant_key(name: str) -> str:
    """Group transactions by merchant.

    Mirrors ``lower(trim(name))`` — the grouping analytics already uses for
    recurring detection and top-merchant contributors — with the internal
    whitespace collapse the import dedupe applies, so the Python-side key and
    the SQL-side one agree.
    """
    return _WS_RE.sub(" ", (name or "").strip().lower())


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sql_merchant_key() -> ColumnElement[str]:
    return func.lower(func.trim(Expense.name))


@dataclass(frozen=True)
class TriageMerchant:
    merchant_key: str
    merchant_name: str
    transaction_count: int
    total_amount: Decimal
    current_importance: str
    category_id: str | None
    last_date: str


@dataclass(frozen=True)
class ImportanceCoverage:
    labelled_merchants: int
    unlabelled_merchants: int
    labelled_amount: Decimal
    total_amount: Decimal
    corrections: int
    overrides: int


class ImportanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def log(
        self,
        *,
        merchant_name: str,
        amount: Decimal,
        expense_date: str,
        to_importance: str,
        context: str,
        expense_id: str | None = None,
        category_id: str | None = None,
        from_importance: str | None = None,
        from_source: str | None = None,
    ) -> ImportanceCorrection:
        """Append one decision to the log.

        Not flushed: callers are already inside a unit of work and the log must
        commit or roll back with the write it describes, never independently.
        """
        if to_importance not in VALID_IMPORTANCE:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"Importance must be one of {sorted(VALID_IMPORTANCE)}, got {to_importance!r}",
            )
        if context not in VALID_CONTEXT:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"Correction context must be one of {sorted(VALID_CONTEXT)}, got {context!r}",
            )
        row = ImportanceCorrection(
            id=str(uuid4()),
            expense_id=expense_id,
            merchant_key=merchant_key(merchant_name),
            merchant_name=merchant_name.strip(),
            category_id=category_id,
            amount=amount,
            expense_date=expense_date,
            from_importance=from_importance if from_importance in VALID_IMPORTANCE else None,
            from_source=from_source if from_source in VALID_SOURCE else None,
            to_importance=to_importance,
            context=context,
            created_at=_now_iso(),
        )
        self.session.add(row)
        return row

    def log_for_expense(
        self,
        expense: Expense,
        *,
        to_importance: str,
        context: str,
    ) -> ImportanceCorrection:
        """Log a decision about an existing row, BEFORE its importance is mutated."""
        return self.log(
            expense_id=expense.id,
            merchant_name=expense.name,
            category_id=expense.category_id,
            amount=expense.amount,
            expense_date=expense.date,
            from_importance=expense.importance,
            from_source=expense.importance_source,
            to_importance=to_importance,
            context=context,
        )

    async def triage_queue(self, *, limit: int = 20) -> list[TriageMerchant]:
        """Merchants with no hand-set importance yet, biggest spend first.

        A merchant is "unlabelled" when NO transaction of its own carries
        ``importance_source='manual'``. Ordering by total spend is what makes
        the queue worth working: labelling the top handful of merchants covers
        the majority of spend, so the classification becomes meaningful long
        before every transaction has been reviewed.
        """
        if limit < 0:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, "Limit must be >= 0.")
        if limit == 0:
            return []

        key = _sql_merchant_key()
        is_manual = func.max(case((Expense.importance_source == "manual", 1), else_=0))
        stmt = (
            select(
                key.label("merchant_key"),
                func.count(Expense.id).label("txn_count"),
                func.sum(Expense.amount).label("total"),
                func.max(Expense.date).label("last_date"),
            )
            .group_by(key)
            .having(is_manual == 0)
            .order_by(func.sum(Expense.amount).desc(), key)
            .limit(limit)
        )
        grouped = list((await self.session.execute(stmt)).all())
        if not grouped:
            return []

        keys = [row.merchant_key for row in grouped]
        detail_stmt = select(
            key.label("merchant_key"),
            Expense.name,
            Expense.importance,
            Expense.category_id,
            Expense.amount,
        ).where(key.in_(keys))
        names: dict[str, Counter[str]] = {k: Counter() for k in keys}
        importances: dict[str, Counter[str]] = {k: Counter() for k in keys}
        categories: dict[str, Counter[str]] = {k: Counter() for k in keys}
        for detail in (await self.session.execute(detail_stmt)).all():
            names[detail.merchant_key][detail.name.strip()] += 1
            # Weight the current-importance vote by spend, not by row count, so
            # the value shown as "currently" matches what dominates the total
            # the user is looking at.
            importances[detail.merchant_key][detail.importance] += int(detail.amount * 100)
            categories[detail.merchant_key][detail.category_id] += 1

        items: list[TriageMerchant] = []
        for row in grouped:
            k = row.merchant_key
            top_name = names[k].most_common(1)
            top_importance = importances[k].most_common(1)
            top_category = categories[k].most_common(1)
            items.append(
                TriageMerchant(
                    merchant_key=k,
                    merchant_name=top_name[0][0] if top_name else k,
                    transaction_count=int(row.txn_count),
                    total_amount=Decimal(row.total or 0),
                    current_importance=top_importance[0][0] if top_importance else "important",
                    category_id=top_category[0][0] if top_category else None,
                    last_date=row.last_date or "",
                )
            )
        return items

    async def apply_triage(self, *, key: str, importance: str) -> int:
        """Label a whole merchant, and record the decision.

        Applies retroactively (it is the only way the existing history gets
        labelled at all) but never touches a row already marked ``'manual'`` —
        a per-transaction decision is more specific than a merchant-wide one
        and outranks it.

        Rows whose importance already matches are still marked ``'manual'``:
        the point of the queue is to turn an unattributed default into a
        confirmed label, and a confirmation is as much a signal as a flip.
        """
        if importance not in VALID_IMPORTANCE:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"Importance must be one of {sorted(VALID_IMPORTANCE)}, got {importance!r}",
            )
        normalized = merchant_key(key)
        if not normalized:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, "Merchant cannot be blank.")

        rows = list(
            (
                await self.session.scalars(
                    select(Expense).where(
                        _sql_merchant_key() == normalized,
                        Expense.importance_source != "manual",
                    )
                )
            ).all()
        )
        for row in rows:
            self.log_for_expense(row, to_importance=importance, context="triage")
            row.importance = importance
            row.importance_source = "manual"
        await self.session.flush()
        return len(rows)

    async def coverage(self) -> ImportanceCoverage:
        """How much of the history is hand-labelled, and how much was corrected."""
        key = _sql_merchant_key()
        is_manual = func.max(case((Expense.importance_source == "manual", 1), else_=0))
        per_merchant = list(
            (await self.session.execute(select(is_manual.label("has_manual")).group_by(key))).all()
        )
        labelled_merchants = sum(1 for row in per_merchant if row.has_manual)

        totals = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(Expense.amount), 0).label("total"),
                    func.coalesce(
                        func.sum(
                            case((Expense.importance_source == "manual", Expense.amount), else_=0)
                        ),
                        0,
                    ).label("labelled"),
                )
            )
        ).one()

        correction_totals = (
            await self.session.execute(
                select(
                    func.count(ImportanceCorrection.id).label("corrections"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    ImportanceCorrection.from_importance
                                    != ImportanceCorrection.to_importance,
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("overrides"),
                )
            )
        ).one()

        return ImportanceCoverage(
            labelled_merchants=labelled_merchants,
            unlabelled_merchants=len(per_merchant) - labelled_merchants,
            labelled_amount=Decimal(totals.labelled or 0),
            total_amount=Decimal(totals.total or 0),
            corrections=int(correction_totals.corrections or 0),
            overrides=int(correction_totals.overrides or 0),
        )
