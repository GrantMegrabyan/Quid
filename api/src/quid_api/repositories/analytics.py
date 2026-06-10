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

#: Diagnosis baseline: trailing N complete months before the latest complete month.
_BASELINE_MONTHS = 6
#: Increases below BOTH floors roll into a single "everything else" line.
_NOISE_FLOOR_ABS = Decimal("10.00")
_NOISE_FLOOR_PCT = 10.0
#: Max contributing merchants returned per increased category.
_CONTRIBUTOR_LIMIT = 3

#: Savings detectors scan this many trailing complete months.
_SAVINGS_WINDOW_MONTHS = 12
#: A (merchant, amount) group is "recurring" at this many distinct months.
_RECURRING_MIN_MONTHS = 3
#: Price creep: the higher amount must appear in at least this many
#: CONSECUTIVE months after the established group's last month.
_CREEP_MIN_NEW_MONTHS = 2
#: New recurring: merchant's first-ever transaction within this many months.
_NEW_RECURRING_RECENT_MONTHS = 4
#: Habit spend: >= this many transactions at <= this average ticket.
_HABIT_MIN_COUNT = 6
_HABIT_MAX_AVG_TICKET = Decimal("20.00")
_HABIT_LIMIT = 5
#: Recurring stack: group counts as active if seen within this many months.
_STACK_ACTIVE_WITHIN_MONTHS = 2


def _month_add(month: str, delta: int) -> str:
    """Add ``delta`` calendar months to a ``YYYY-MM`` key."""
    idx = int(month[:4]) * 12 + int(month[5:7]) - 1 + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _months_between(a: str, b: str) -> int:
    """Calendar-month distance ``b - a`` between two ``YYYY-MM`` keys."""
    return (int(b[:4]) * 12 + int(b[5:7])) - (int(a[:4]) * 12 + int(a[5:7]))


def _is_consecutive(months: list[str]) -> bool:
    return all(_months_between(months[i], months[i + 1]) == 1 for i in range(len(months) - 1))


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
class RecurringItem:
    name: str
    amount: Decimal
    occurrences: int
    months_covered: int
    first_month: str
    last_month: str
    monthly_estimate: Decimal


@dataclass(frozen=True)
class LargeTransaction:
    id: str
    name: str
    display_name: str | None
    amount: Decimal
    date: str
    category_id: str | None
    category_name: str | None
    category_color: str | None


@dataclass(frozen=True)
class ImportanceTrendPoint:
    month: str
    total: Decimal


@dataclass(frozen=True)
class ImportanceTrendSeries:
    importance: str
    total: Decimal
    points: list[ImportanceTrendPoint]


@dataclass(frozen=True)
class WeekdayPoint:
    weekday: int  # 0=Monday .. 6=Sunday
    total: Decimal
    count: int


@dataclass(frozen=True)
class DiagnosisContributor:
    merchant: str
    current: Decimal
    baseline: Decimal
    delta: Decimal
    is_new: bool


@dataclass(frozen=True)
class DiagnosisTransaction:
    id: str
    name: str
    display_name: str | None
    amount: Decimal
    date: str


@dataclass(frozen=True)
class DiagnosisIncrease:
    category_id: str
    category_name: str
    color: str
    current: Decimal
    baseline: Decimal
    delta: Decimal
    percent_change: float | None  # None when there is no baseline (new spending)
    is_new: bool
    contributors: list[DiagnosisContributor]
    transactions: list[DiagnosisTransaction]


@dataclass(frozen=True)
class DiagnosisDecrease:
    category_id: str
    category_name: str
    color: str
    current: Decimal
    baseline: Decimal
    delta: Decimal  # negative


@dataclass(frozen=True)
class DiagnosisResult:
    latest_month: str | None
    baseline_from: str | None
    baseline_to: str | None
    baseline_month_count: int
    total_current: Decimal
    total_baseline: Decimal
    increases: list[DiagnosisIncrease]
    other_increases_total: Decimal
    other_increases_count: int
    decreases: list[DiagnosisDecrease]


@dataclass
class _RecurringGroup:
    key: str
    amount: Decimal
    months: list[str]


@dataclass(frozen=True)
class PriceCreepItem:
    name: str
    old_amount: Decimal
    new_amount: Decimal
    monthly_delta: Decimal
    annual_delta: Decimal
    since_month: str


@dataclass(frozen=True)
class NewRecurringItem:
    name: str
    amount: Decimal
    first_month: str
    annual_cost: Decimal


@dataclass(frozen=True)
class HabitItem:
    name: str
    count: int
    total: Decimal
    average: Decimal


@dataclass(frozen=True)
class RecurringStackItem:
    name: str
    amount: Decimal
    months_covered: int
    first_month: str
    last_month: str
    monthly_estimate: Decimal


@dataclass(frozen=True)
class SavingsResult:
    latest_month: str | None
    window_from: str | None
    price_creep: list[PriceCreepItem]
    new_recurring: list[NewRecurringItem]
    habits: list[HabitItem]
    stack_items: list[RecurringStackItem]
    stack_monthly_total: Decimal
    stack_annual_total: Decimal


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
        self, *, date_from: str | None = None, date_to: str | None = None, limit: int = 8
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
        if len(series) > limit:
            top = series[:limit]
            other_total = sum((s.total for s in series[limit:]), _ZERO)
            other_points: dict[str, Decimal] = {}
            for s in series[limit:]:
                for month_key, amt in s.points.items():
                    other_points[month_key] = other_points.get(month_key, _ZERO) + amt
            top.append(
                CategoryTrendSeries(
                    category_id="__other__",
                    category_name="Other",
                    color="#6c7086",
                    total=other_total,
                    points=other_points,
                )
            )
            return top
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

    async def recurring(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> list[RecurringItem]:
        month = _MONTH_EXPR.label("month")
        key = func.lower(func.trim(Expense.name)).label("merchant_key")
        stmt = (
            select(
                func.max(Expense.name),
                Expense.amount,
                func.count(),
                func.count(func.distinct(month)),
                func.min(month),
                func.max(month),
            )
            .group_by(key, Expense.amount)
            .having(func.count(func.distinct(month)) >= 3)
            .order_by(Expense.amount.desc())
        )
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()
        return [
            RecurringItem(
                name=str(name),
                amount=_as_decimal(amount),
                occurrences=int(occurrences),
                months_covered=int(months_covered),
                first_month=str(first_month),
                last_month=str(last_month),
                monthly_estimate=_as_decimal(amount),
            )
            for name, amount, occurrences, months_covered, first_month, last_month in rows
        ]

    async def large_transactions(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
    ) -> tuple[list[LargeTransaction], Decimal]:
        category_name = Category.name.label("category_name")
        category_color = Category.color.label("category_color")
        stmt = (
            select(
                Expense.id,
                Expense.name,
                Expense.display_name,
                Expense.amount,
                Expense.date,
                Expense.category_id,
                category_name,
                category_color,
            )
            .join(Category, Category.id == Expense.category_id, isouter=True)
            .order_by(Expense.amount.desc(), Expense.date.desc())
            .limit(limit)
        )
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()

        total_stmt = select(func.sum(Expense.amount))
        total_stmt = self._window(total_stmt, date_from, date_to)
        total = _as_decimal((await self.session.execute(total_stmt)).scalar_one_or_none())

        return (
            [
                LargeTransaction(
                    id=str(rid),
                    name=str(name),
                    display_name=None if display_name is None else str(display_name),
                    amount=_as_decimal(amount),
                    date=str(date),
                    category_id=None if category_id is None else str(category_id),
                    category_name=None if category_name is None else str(category_name),
                    category_color=None if category_color is None else str(category_color),
                )
                for rid, name, display_name, amount, date, category_id, category_name, category_color in rows
            ],
            total,
        )

    async def distribution(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> list[Decimal]:
        stmt = select(Expense.amount).order_by(Expense.amount)
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_as_decimal(v) for v in rows]

    async def importance_trend(
        self, *, date_from: str | None = None, date_to: str | None = None
    ) -> tuple[list[str], list[ImportanceTrendSeries]]:
        month = _MONTH_EXPR.label("month")
        stmt = (
            select(Expense.importance, month, func.sum(Expense.amount))
            .group_by(Expense.importance, month)
            .order_by(month)
        )
        stmt = self._window(stmt, date_from, date_to)
        rows = (await self.session.execute(stmt)).all()
        months = sorted({str(month_key) for _, month_key, _ in rows})
        by_importance: dict[str, dict[str, Decimal]] = {
            k: {} for k in ("essential", "important", "discretionary")
        }
        totals: dict[str, Decimal] = dict.fromkeys(by_importance, _ZERO)
        for importance, month_key, amount in rows:
            imp = str(importance)
            amt = _as_decimal(amount)
            by_importance.setdefault(imp, {})[str(month_key)] = amt
            totals[imp] = totals.get(imp, _ZERO) + amt
        series = [
            ImportanceTrendSeries(
                importance=imp,
                total=totals.get(imp, _ZERO),
                points=[
                    ImportanceTrendPoint(month=m, total=by_importance.get(imp, {}).get(m, _ZERO))
                    for m in months
                ],
            )
            for imp in ("essential", "important", "discretionary")
        ]
        return months, series

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

    async def diagnosis(self, *, as_of: str) -> DiagnosisResult:
        """'What went up': latest complete month vs the trailing-average baseline.

        The baseline is each category's mean monthly spend over the (up to)
        ``_BASELINE_MONTHS`` complete months before the latest complete month,
        dividing by the WINDOW LENGTH so zero-spend months count as 0.
        """
        try:
            current_month = validate_iso_date(as_of)[:7]
        except ValueError as exc:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, str(exc)) from exc

        month = _MONTH_EXPR.label("month")
        month_rows = (
            (
                await self.session.execute(
                    select(month).where(current_month > _MONTH_EXPR).group_by(month).order_by(month)
                )
            )
            .scalars()
            .all()
        )
        months = [str(m) for m in month_rows]
        if not months:
            return DiagnosisResult(
                latest_month=None,
                baseline_from=None,
                baseline_to=None,
                baseline_month_count=0,
                total_current=_ZERO,
                total_baseline=_ZERO,
                increases=[],
                other_increases_total=_ZERO,
                other_increases_count=0,
                decreases=[],
            )

        latest = months[-1]
        first_data = months[0]
        cur_by_cat = await self._category_month_totals(latest, latest)
        total_current = sum(cur_by_cat.values(), _ZERO)

        base_to = _month_add(latest, -1)
        base_from = max(_month_add(latest, -_BASELINE_MONTHS), first_data)
        if base_to < first_data:
            # Only one complete month of history: nothing to compare against.
            return DiagnosisResult(
                latest_month=latest,
                baseline_from=None,
                baseline_to=None,
                baseline_month_count=0,
                total_current=total_current,
                total_baseline=_ZERO,
                increases=[],
                other_increases_total=_ZERO,
                other_increases_count=0,
                decreases=[],
            )
        base_count = _months_between(base_from, base_to) + 1

        base_totals = await self._category_month_totals(base_from, base_to)
        base_div = Decimal(base_count)
        base_by_cat = {cid: (t / base_div).quantize(_ZERO) for cid, t in base_totals.items()}
        total_baseline = sum(base_by_cat.values(), _ZERO)

        all_ids = set(cur_by_cat) | set(base_by_cat)
        names = await self._category_names(list(all_ids))

        kept: list[tuple[str, Decimal, Decimal, Decimal, float | None, bool]] = []
        other_total = _ZERO
        other_count = 0
        decreases: list[DiagnosisDecrease] = []
        for cid in all_ids:
            current = cur_by_cat.get(cid, _ZERO)
            baseline = base_by_cat.get(cid, _ZERO)
            delta = current - baseline
            name, color = names.get(cid, (cid, color_for_category_id(cid)))
            if delta > _ZERO:
                pct = float(delta / baseline * 100) if baseline > _ZERO else None
                if delta >= _NOISE_FLOOR_ABS or (pct is not None and pct >= _NOISE_FLOOR_PCT):
                    kept.append((cid, current, baseline, delta, pct, baseline == _ZERO))
                else:
                    other_total += delta
                    other_count += 1
            elif delta < _ZERO:
                decreases.append(
                    DiagnosisDecrease(
                        category_id=cid,
                        category_name=name,
                        color=color,
                        current=current,
                        baseline=baseline,
                        delta=delta,
                    )
                )

        kept.sort(key=lambda item: item[3], reverse=True)
        decreases.sort(key=lambda d: d.delta)

        kept_ids = [cid for cid, *_ in kept]
        cur_merchants = await self._merchant_category_totals(latest, latest, kept_ids)
        base_merchants = await self._merchant_category_totals(base_from, base_to, kept_ids)
        txns_by_cat = await self._transactions_for_month(latest, kept_ids)

        increases: list[DiagnosisIncrease] = []
        for cid, current, baseline, delta, pct, is_new in kept:
            name, color = names.get(cid, (cid, color_for_category_id(cid)))
            contributors: list[DiagnosisContributor] = []
            for mkey, (label, cur_total) in cur_merchants.get(cid, {}).items():
                base_pair = base_merchants.get(cid, {}).get(mkey)
                m_base = (base_pair[1] / base_div).quantize(_ZERO) if base_pair else _ZERO
                m_delta = cur_total - m_base
                if m_delta > _ZERO:
                    contributors.append(
                        DiagnosisContributor(
                            merchant=label,
                            current=cur_total,
                            baseline=m_base,
                            delta=m_delta,
                            is_new=base_pair is None,
                        )
                    )
            contributors.sort(key=lambda c: c.delta, reverse=True)
            increases.append(
                DiagnosisIncrease(
                    category_id=cid,
                    category_name=name,
                    color=color,
                    current=current,
                    baseline=baseline,
                    delta=delta,
                    percent_change=pct,
                    is_new=is_new,
                    contributors=contributors[:_CONTRIBUTOR_LIMIT],
                    transactions=txns_by_cat.get(cid, []),
                )
            )

        return DiagnosisResult(
            latest_month=latest,
            baseline_from=base_from,
            baseline_to=base_to,
            baseline_month_count=base_count,
            total_current=total_current,
            total_baseline=total_baseline,
            increases=increases,
            other_increases_total=other_total,
            other_increases_count=other_count,
            decreases=decreases,
        )

    async def savings(self, *, as_of: str) -> SavingsResult:
        """Saving-opportunity detectors over the trailing 12 complete months."""
        try:
            current_month = validate_iso_date(as_of)[:7]
        except ValueError as exc:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, str(exc)) from exc

        latest_raw = (
            await self.session.execute(
                select(func.max(_MONTH_EXPR)).where(_MONTH_EXPR < current_month)  # noqa: SIM300
            )
        ).scalar_one_or_none()
        if latest_raw is None:
            return SavingsResult(
                latest_month=None,
                window_from=None,
                price_creep=[],
                new_recurring=[],
                habits=[],
                stack_items=[],
                stack_monthly_total=_ZERO,
                stack_annual_total=_ZERO,
            )
        latest = str(latest_raw)
        window_from = _month_add(latest, -(_SAVINGS_WINDOW_MONTHS - 1))

        key = func.lower(func.trim(Expense.name)).label("merchant_key")
        month = _MONTH_EXPR.label("month")
        group_stmt = (
            select(key, func.max(Expense.name), Expense.amount, month)
            .where(_MONTH_EXPR >= window_from, _MONTH_EXPR <= latest)  # noqa: SIM300
            .group_by(key, Expense.amount, month)
            .order_by(month)
        )
        rows = (await self.session.execute(group_stmt)).all()
        groups: dict[tuple[str, Decimal], _RecurringGroup] = {}
        labels: dict[str, str] = {}
        for mkey, label, amount, month_key in rows:
            k = str(mkey)
            amt = _as_decimal(amount)
            labels[k] = str(label)
            group = groups.setdefault((k, amt), _RecurringGroup(key=k, amount=amt, months=[]))
            group.months.append(str(month_key))

        first_stmt = select(key, func.min(_MONTH_EXPR)).group_by(key)
        first_ever = {str(k): str(m) for k, m in (await self.session.execute(first_stmt)).all()}

        by_merchant: dict[str, list[_RecurringGroup]] = {}
        for group in groups.values():
            by_merchant.setdefault(group.key, []).append(group)

        price_creep: list[PriceCreepItem] = []
        for mkey, merchant_groups in by_merchant.items():
            established = [g for g in merchant_groups if len(g.months) >= _RECURRING_MIN_MONTHS]
            best: tuple[_RecurringGroup, _RecurringGroup] | None = None
            for est in established:
                for cand in merchant_groups:
                    if cand.amount <= est.amount:
                        continue
                    if len(cand.months) < _CREEP_MIN_NEW_MONTHS:
                        continue
                    if cand.months[0] <= est.months[-1]:
                        continue
                    if not _is_consecutive(cand.months):
                        continue
                    if best is None or cand.months[0] > best[1].months[0]:
                        best = (est, cand)
            if best is not None:
                est, cand = best
                delta = (cand.amount - est.amount).quantize(_ZERO)
                price_creep.append(
                    PriceCreepItem(
                        name=labels[mkey],
                        old_amount=est.amount,
                        new_amount=cand.amount,
                        monthly_delta=delta,
                        annual_delta=(delta * 12).quantize(_ZERO),
                        since_month=cand.months[0],
                    )
                )
        price_creep.sort(key=lambda c: c.annual_delta, reverse=True)

        recent_cutoff = _month_add(latest, -(_NEW_RECURRING_RECENT_MONTHS - 1))
        new_recurring = [
            NewRecurringItem(
                name=labels[g.key],
                amount=g.amount,
                first_month=g.months[0],
                annual_cost=(g.amount * 12).quantize(_ZERO),
            )
            for g in groups.values()
            if len(g.months) >= _RECURRING_MIN_MONTHS and first_ever.get(g.key, "") >= recent_cutoff
        ]
        new_recurring.sort(key=lambda n: n.annual_cost, reverse=True)

        habit_stmt = (
            select(func.max(Expense.name), func.count(), func.sum(Expense.amount))
            .where(_MONTH_EXPR == latest)  # noqa: SIM300
            .group_by(key)
            .having(func.count() >= _HABIT_MIN_COUNT)
        )
        habits: list[HabitItem] = []
        for label, count, total in (await self.session.execute(habit_stmt)).all():
            total_d = _as_decimal(total)
            average = (total_d / int(count)).quantize(_ZERO)
            if average <= _HABIT_MAX_AVG_TICKET:
                habits.append(
                    HabitItem(name=str(label), count=int(count), total=total_d, average=average)
                )
        habits.sort(key=lambda h: h.total, reverse=True)
        habits = habits[:_HABIT_LIMIT]

        active_cutoff = _month_add(latest, -(_STACK_ACTIVE_WITHIN_MONTHS - 1))
        stack_items: list[RecurringStackItem] = []
        for group in groups.values():
            if len(group.months) < _RECURRING_MIN_MONTHS:
                continue
            if group.months[-1] < active_cutoff:
                continue
            span = _months_between(group.months[0], group.months[-1]) + 1
            estimate = min(
                group.amount,
                (group.amount * Decimal(len(group.months)) / Decimal(span)).quantize(_ZERO),
            )
            stack_items.append(
                RecurringStackItem(
                    name=labels[group.key],
                    amount=group.amount,
                    months_covered=len(group.months),
                    first_month=group.months[0],
                    last_month=group.months[-1],
                    monthly_estimate=estimate,
                )
            )
        stack_items.sort(key=lambda s: s.monthly_estimate, reverse=True)
        stack_monthly_total = sum((s.monthly_estimate for s in stack_items), _ZERO)

        return SavingsResult(
            latest_month=latest,
            window_from=window_from,
            price_creep=price_creep,
            new_recurring=new_recurring,
            habits=habits,
            stack_items=stack_items,
            stack_monthly_total=stack_monthly_total,
            stack_annual_total=(stack_monthly_total * 12).quantize(_ZERO),
        )

    async def _category_month_totals(self, month_from: str, month_to: str) -> dict[str, Decimal]:
        stmt = (
            select(Expense.category_id, func.sum(Expense.amount))
            .where(month_from <= _MONTH_EXPR, month_to >= _MONTH_EXPR)
            .group_by(Expense.category_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {str(cid): _as_decimal(total) for cid, total in rows}

    async def _merchant_category_totals(
        self, month_from: str, month_to: str, category_ids: list[str]
    ) -> dict[str, dict[str, tuple[str, Decimal]]]:
        """category_id -> merchant_key -> (display label, total)."""
        if not category_ids:
            return {}
        key = func.lower(func.trim(Expense.name)).label("merchant_key")
        stmt = (
            select(Expense.category_id, key, func.max(Expense.name), func.sum(Expense.amount))
            .where(
                month_from <= _MONTH_EXPR,
                month_to >= _MONTH_EXPR,
                Expense.category_id.in_(category_ids),
            )
            .group_by(Expense.category_id, key)
        )
        rows = (await self.session.execute(stmt)).all()
        out: dict[str, dict[str, tuple[str, Decimal]]] = {}
        for cid, mkey, label, total in rows:
            out.setdefault(str(cid), {})[str(mkey)] = (str(label), _as_decimal(total))
        return out

    async def _transactions_for_month(
        self, month_key: str, category_ids: list[str]
    ) -> dict[str, list[DiagnosisTransaction]]:
        if not category_ids:
            return {}
        stmt = (
            select(
                Expense.id,
                Expense.name,
                Expense.display_name,
                Expense.amount,
                Expense.date,
                Expense.category_id,
            )
            .where(_MONTH_EXPR == month_key, Expense.category_id.in_(category_ids))  # noqa: SIM300
            .order_by(Expense.amount.desc(), Expense.date.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        out: dict[str, list[DiagnosisTransaction]] = {}
        for rid, name, display_name, amount, date, cid in rows:
            out.setdefault(str(cid), []).append(
                DiagnosisTransaction(
                    id=str(rid),
                    name=str(name),
                    display_name=None if display_name is None else str(display_name),
                    amount=_as_decimal(amount),
                    date=str(date),
                )
            )
        return out

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
    "DiagnosisContributor",
    "DiagnosisDecrease",
    "DiagnosisIncrease",
    "DiagnosisResult",
    "DiagnosisTransaction",
    "HabitItem",
    "ImportancePoint",
    "ImportanceTrendPoint",
    "ImportanceTrendSeries",
    "LargeTransaction",
    "MonthlyTotal",
    "NewRecurringItem",
    "PriceCreepItem",
    "RecurringItem",
    "RecurringStackItem",
    "SavingsResult",
    "TopMerchant",
    "WeekdayPoint",
]
