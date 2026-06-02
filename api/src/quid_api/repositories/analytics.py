"""Server-side analytics aggregations over the ``expenses`` table.

The dashboard does its single-month aggregation client-side (it already fetches
one month's rows). Analytics, by contrast, spans many months / all of history,
so aggregating in SQL is the right call — we never want to ship thousands of
rows to the browser just to sum them.

Date handling: ``expenses.date`` is TEXT holding either ``YYYY-MM-DD`` or
``YYYY-MM-DDTHH:MM:SS``. Both forms share the same 7-char ``YYYY-MM`` month
prefix and 10-char ``YYYY-MM-DD`` day prefix, and both sort lexically, so:

* month grouping uses ``substr(date, 1, 7)``
* day-of-week uses ``strftime('%w', substr(date, 1, 10))`` (SQLite; 0=Sunday)
* a half-open ``[from, exclusive_upper)`` range filters a window, where
  ``exclusive_upper`` is the first day AFTER the inclusive ``date_to`` so a
  ``...T23:59:59`` row on the boundary day is kept (mirrors
  ``ExpenseRepository.list_all``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from quid_api.category_helpers import UNCATEGORIZED_ID, color_for_category_id
from quid_api.datelib import validate_iso_date
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category, Expense

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql import Select


_ZERO = Decimal("0.00")

#: 7-char month prefix, e.g. "2026-05". Works for both date-only and
#: timestamped expense dates.
_MONTH_EXPR = func.substr(Expense.date, 1, 7)
#: 10-char day prefix, e.g. "2026-05-31".
_DAY_EXPR = func.substr(Expense.date, 1, 10)


def _as_decimal(value: object) -> Decimal:
    """Coerce a SUM() result (which may be None on no rows) to a 2dp Decimal."""
    if value is None:
        return _ZERO
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _exclusive_upper(date_to: str) -> str:
    inclusive = validate_iso_date(date_to)
    return (date_cls.fromisoformat(inclusive) + timedelta(days=1)).isoformat()


@dataclass(frozen=True)
class MonthlyTotal:
    month: str
    total: Decimal
    count: int


@dataclass(frozen=True)
class CategoryTrendSeries:
    category_id: str
    category_name: str
    color: str
    total: Decimal
    points: dict[str, Decimal]  # month -> total


@dataclass(frozen=True)
class CategoryMover:
    category_id: str
    category_name: str
    color: str
    current: Decimal
    previous: Decimal


@dataclass(frozen=True)
class TopMerchant:
    merchant: str
    total: Decimal
    count: int


@dataclass(frozen=True)
class ImportancePoint:
    importance: str
    total: Decimal
    count: int


@dataclass(frozen=True)
class WeekdayPoint:
    weekday: int  # 0=Monday .. 6=Sunday
    total: Decimal
    count: int


class AnalyticsRepository:
    """Read-only aggregation queries. No writes, no commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _window(self, stmt: Select[Any], date_from: str | None, date_to: str | None) -> Select[Any]:
        """Apply an optional half-open ``[from, exclusive_upper)`` date window."""
        if date_from is not None:
            try:
                lower = validate_iso_date(date_from)
            except ValueError as exc:
                raise RepositoryError(RepositoryErrorCode.VALIDATION, str(exc)) from exc
            stmt = stmt.where(Expense.date >= lower)
        if date_to is not None:
            try:
                upper = _exclusive_upper(date_to)
            except ValueError as exc:
                raise RepositoryError(RepositoryErrorCode.VALIDATION, str(exc)) from exc
            stmt = stmt.where(Expense.date < upper)
        return stmt

    async def monthly_totals(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> list[MonthlyTotal]:
        """Total spend + transaction count per calendar month, ascending."""
        month = _MONTH_EXPR.label("month")
        stmt = select(month, func.sum(Expense.amount), func.count()).group_by(month).order_by(month)
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()
        return [
            MonthlyTotal(month=str(r[0]), total=_as_decimal(r[1]), count=int(r[2])) for r in rows
        ]

    async def category_trends(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> list[CategoryTrendSeries]:
        """Per-category spend per month. One series per category that has spend.

        Ordered by overall spend descending so the biggest spenders draw first.
        """
        month = _MONTH_EXPR.label("month")
        stmt = (
            select(
                Expense.category_id,
                month,
                func.sum(Expense.amount),
            )
            .group_by(Expense.category_id, month)
            .order_by(month)
        )
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()

        # Aggregate into per-category buckets.
        points: dict[str, dict[str, Decimal]] = {}
        totals: dict[str, Decimal] = {}
        for category_id, month_key, amount in rows:
            cid = str(category_id)
            amt = _as_decimal(amount)
            points.setdefault(cid, {})[str(month_key)] = amt
            totals[cid] = totals.get(cid, _ZERO) + amt

        names = await self._category_names(list(totals.keys()))

        series = [
            CategoryTrendSeries(
                category_id=cid,
                category_name=names.get(cid, (cid, ""))[0],
                color=names.get(cid, (cid, color_for_category_id(cid)))[1],
                total=total,
                points=points.get(cid, {}),
            )
            for cid, total in totals.items()
        ]
        series.sort(key=lambda s: s.total, reverse=True)
        return series

    async def category_movers(
        self,
        *,
        current_from: str,
        current_to: str,
        previous_from: str,
        previous_to: str,
    ) -> list[CategoryMover]:
        """Per-category spend in the current window vs the previous window.

        Sorted by absolute delta descending so the biggest movers (up or down)
        come first.
        """
        current = await self._category_totals(current_from, current_to)
        previous = await self._category_totals(previous_from, previous_to)
        all_ids = set(current) | set(previous)
        names = await self._category_names(list(all_ids))

        movers = [
            CategoryMover(
                category_id=cid,
                category_name=names.get(cid, (cid, ""))[0],
                color=names.get(cid, (cid, color_for_category_id(cid)))[1],
                current=current.get(cid, _ZERO),
                previous=previous.get(cid, _ZERO),
            )
            for cid in all_ids
        ]
        movers.sort(key=lambda m: abs(m.current - m.previous), reverse=True)
        return movers

    async def top_merchants(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 10,
    ) -> list[TopMerchant]:
        """Top merchants by spend, grouping on ``lower(trim(name))``.

        There is no dedicated merchant column; ``Expense.name`` is the merchant
        string. We group case-/whitespace-insensitively but display the most
        recent original-cased name for the group (via MAX over the raw name,
        good enough for a label).
        """
        if limit < 0:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, "Limit must be >= 0.")
        key = func.lower(func.trim(Expense.name)).label("merchant_key")
        stmt = (
            select(
                func.max(Expense.name),
                func.sum(Expense.amount),
                func.count(),
            )
            .group_by(key)
            .order_by(func.sum(Expense.amount).desc())
            .limit(limit)
        )
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()
        return [
            TopMerchant(merchant=str(r[0]), total=_as_decimal(r[1]), count=int(r[2])) for r in rows
        ]

    async def importance_breakdown(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> list[ImportancePoint]:
        """Spend + count grouped by importance tier."""
        stmt = (
            select(Expense.importance, func.sum(Expense.amount), func.count())
            .group_by(Expense.importance)
            .order_by(func.sum(Expense.amount).desc())
        )
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()
        return [
            ImportancePoint(importance=str(r[0]), total=_as_decimal(r[1]), count=int(r[2]))
            for r in rows
        ]

    async def weekday_breakdown(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> list[WeekdayPoint]:
        """Spend + count grouped by day-of-week (Mon..Sun), filling gaps with 0.

        SQLite's ``strftime('%w', ...)`` returns 0=Sunday..6=Saturday; we remap
        to 0=Monday..6=Sunday so the UI can render a Mon-first week.
        """
        dow = func.strftime("%w", _DAY_EXPR).label("dow")
        stmt = select(dow, func.sum(Expense.amount), func.count()).group_by(dow).order_by(dow)
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()

        # Map sqlite 0=Sun..6=Sat -> 0=Mon..6=Sun.
        sqlite_to_mon = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
        by_weekday: dict[int, WeekdayPoint] = {}
        for raw_dow, amount, count in rows:
            if raw_dow is None:
                continue
            weekday = sqlite_to_mon[int(raw_dow)]
            by_weekday[weekday] = WeekdayPoint(
                weekday=weekday, total=_as_decimal(amount), count=int(count)
            )
        return [
            by_weekday.get(day, WeekdayPoint(weekday=day, total=_ZERO, count=0)) for day in range(7)
        ]

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _category_totals(
        self, date_from: str | None, date_to: str | None
    ) -> dict[str, Decimal]:
        stmt = select(Expense.category_id, func.sum(Expense.amount)).group_by(Expense.category_id)
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()
        return {str(cid): _as_decimal(total) for cid, total in rows}

    async def _category_names(self, category_ids: list[str]) -> dict[str, tuple[str, str]]:
        """Map category id -> (name, color). Unknown ids fall back to a derived
        name/colour so an orphaned expense still labels sensibly."""
        if not category_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Category.id, Category.name, Category.color).where(
                    Category.id.in_(category_ids)
                )
            )
        ).all()
        mapping: dict[str, tuple[str, str]] = {
            str(cid): (str(name), str(color)) for cid, name, color in rows
        }
        for cid in category_ids:
            if cid not in mapping:
                label = "Uncategorized" if cid == UNCATEGORIZED_ID else cid
                mapping[cid] = (label, color_for_category_id(cid))
        return mapping


__all__ = [
    "AnalyticsRepository",
    "CategoryMover",
    "CategoryTrendSeries",
    "ImportancePoint",
    "MonthlyTotal",
    "TopMerchant",
    "WeekdayPoint",
]
