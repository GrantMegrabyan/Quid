"""Read-only analytics endpoints (aggregations over expenses).

Endpoints accept an optional ``date_from`` / ``date_to`` (inclusive,
``YYYY-MM-DD``) window. When omitted they cover all of history. The
``category-comparison`` endpoint instead takes two explicit periods so the UI
can ask "this month vs last month" or "this quarter vs last quarter".
"""

from __future__ import annotations

import calendar
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query

from quid_api.datelib import validate_iso_date
from quid_api.db import get_session
from quid_api.repositories.analytics import AnalyticsRepository
from quid_api.schemas import (
    AnalyticsSummaryResponse,
    CategoryComparisonResponse,
    CategoryMoverOut,
    CategoryTrendPointOut,
    CategoryTrendSeriesOut,
    CategoryTrendsResponse,
    DiagnosisContributorOut,
    DiagnosisDecreaseOut,
    DiagnosisIncreaseOut,
    DiagnosisResponse,
    DiagnosisTransactionOut,
    DistributionResponse,
    ImportanceBreakdownPointOut,
    ImportanceBreakdownResponse,
    ImportanceTrendPointOut,
    ImportanceTrendResponse,
    ImportanceTrendSeriesOut,
    LargeTransactionOut,
    LargeTransactionsResponse,
    MonthlyTotalOut,
    MonthlyTotalsResponse,
    RecurringItemOut,
    RecurringResponse,
    TopMerchantOut,
    TopMerchantsResponse,
    WeekdayBreakdownPointOut,
    WeekdayBreakdownResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]

_ZERO = Decimal("0.00")

DateFrom = Annotated[str | None, Query(alias="date_from")]
DateTo = Annotated[str | None, Query(alias="date_to")]
AsOf = Annotated[str | None, Query(alias="as_of")]


def _percent_change(current: Decimal, previous: Decimal) -> float | None:
    """Percent change of ``current`` vs ``previous`` (e.g. 25.0 = +25%).

    ``None`` when there's no previous baseline (avoids a divide-by-zero / a
    misleading "infinite %" badge).
    """
    if previous == _ZERO:
        return None
    return float((current - previous) / previous * 100)


def _month_days(month: str) -> int:
    year, month_num = map(int, month.split("-"))
    return calendar.monthrange(year, month_num)[1]


@router.get("/monthly-totals", response_model=MonthlyTotalsResponse)
async def monthly_totals(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> MonthlyTotalsResponse:
    repo = AnalyticsRepository(session)
    rows = await repo.monthly_totals(date_from=date_from, date_to=date_to)
    total = sum((r.total for r in rows), _ZERO)
    count = sum(r.count for r in rows)
    average = (total / len(rows)).quantize(_ZERO) if rows else _ZERO
    return MonthlyTotalsResponse(
        months=[MonthlyTotalOut(month=r.month, total=r.total, count=r.count) for r in rows],
        total=total,
        average=average,
        count=count,
    )


@router.get("/category-trends", response_model=CategoryTrendsResponse)
async def category_trends(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
) -> CategoryTrendsResponse:
    repo = AnalyticsRepository(session)
    series = await repo.category_trends(date_from=date_from, date_to=date_to, limit=limit)

    # Collect the union of months across all series so the UI gets a single,
    # dense, ascending month axis.
    month_set: set[str] = set()
    for s in series:
        month_set.update(s.points.keys())
    months = sorted(month_set)

    return CategoryTrendsResponse(
        months=months,
        series=[
            CategoryTrendSeriesOut(
                category_id=s.category_id,
                category_name=s.category_name,
                color=s.color,
                total=s.total,
                points=[
                    CategoryTrendPointOut(month=m, total=s.points.get(m, _ZERO)) for m in months
                ],
            )
            for s in series
        ],
    )


@router.get("/category-comparison", response_model=CategoryComparisonResponse)
async def category_comparison(
    session: SessionDep,
    current_from: Annotated[str, Query(alias="current_from")],
    current_to: Annotated[str, Query(alias="current_to")],
    previous_from: Annotated[str, Query(alias="previous_from")],
    previous_to: Annotated[str, Query(alias="previous_to")],
) -> CategoryComparisonResponse:
    repo = AnalyticsRepository(session)
    movers = await repo.category_movers(
        current_from=current_from,
        current_to=current_to,
        previous_from=previous_from,
        previous_to=previous_to,
    )
    current_total = sum((m.current for m in movers), _ZERO)
    previous_total = sum((m.previous for m in movers), _ZERO)
    return CategoryComparisonResponse(
        current_period_label=f"{current_from} → {current_to}",
        previous_period_label=f"{previous_from} → {previous_to}",
        current_total=current_total,
        previous_total=previous_total,
        movers=[
            CategoryMoverOut(
                category_id=m.category_id,
                category_name=m.category_name,
                color=m.color,
                current=m.current,
                previous=m.previous,
                delta=m.current - m.previous,
                percent_change=_percent_change(m.current, m.previous),
            )
            for m in movers
        ],
    )


@router.get("/top-merchants", response_model=TopMerchantsResponse)
async def top_merchants(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> TopMerchantsResponse:
    repo = AnalyticsRepository(session)
    rows = await repo.top_merchants(date_from=date_from, date_to=date_to, limit=limit)
    return TopMerchantsResponse(
        merchants=[TopMerchantOut(merchant=r.merchant, total=r.total, count=r.count) for r in rows]
    )


@router.get("/importance-breakdown", response_model=ImportanceBreakdownResponse)
async def importance_breakdown(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> ImportanceBreakdownResponse:
    repo = AnalyticsRepository(session)
    rows = await repo.importance_breakdown(date_from=date_from, date_to=date_to)
    total = sum((r.total for r in rows), _ZERO)
    return ImportanceBreakdownResponse(
        breakdown=[
            ImportanceBreakdownPointOut(
                importance=r.importance,  # type: ignore[arg-type]
                total=r.total,
                count=r.count,
            )
            for r in rows
        ],
        total=total,
    )


@router.get("/weekday-breakdown", response_model=WeekdayBreakdownResponse)
async def weekday_breakdown(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> WeekdayBreakdownResponse:
    repo = AnalyticsRepository(session)
    rows = await repo.weekday_breakdown(date_from=date_from, date_to=date_to)
    return WeekdayBreakdownResponse(
        breakdown=[
            WeekdayBreakdownPointOut(weekday=r.weekday, total=r.total, count=r.count) for r in rows
        ]
    )


@router.get("/recurring", response_model=RecurringResponse)
async def recurring(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> RecurringResponse:
    repo = AnalyticsRepository(session)
    rows = await repo.recurring(date_from=date_from, date_to=date_to)
    monthly_total = sum((r.monthly_estimate for r in rows), _ZERO)
    return RecurringResponse(
        items=[
            RecurringItemOut(
                name=r.name,
                amount=r.amount,
                occurrences=r.occurrences,
                months_covered=r.months_covered,
                first_month=r.first_month,
                last_month=r.last_month,
                monthly_estimate=r.monthly_estimate,
            )
            for r in rows
        ],
        monthly_total=monthly_total,
        count=len(rows),
    )


@router.get("/large-transactions", response_model=LargeTransactionsResponse)
async def large_transactions(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> LargeTransactionsResponse:
    repo = AnalyticsRepository(session)
    rows, period_total = await repo.large_transactions(
        date_from=date_from, date_to=date_to, limit=limit
    )
    top_total = sum((r.amount for r in rows), _ZERO)
    return LargeTransactionsResponse(
        transactions=[
            LargeTransactionOut(
                id=r.id,
                name=r.name,
                display_name=r.display_name,
                amount=r.amount,
                date=r.date,
                category_id=r.category_id,
                category_name=r.category_name,
                category_color=r.category_color,
            )
            for r in rows
        ],
        period_total=period_total,
        top_share=(float(top_total / period_total) if period_total != _ZERO else None),
    )


@router.get("/distribution", response_model=DistributionResponse)
async def distribution(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> DistributionResponse:
    repo = AnalyticsRepository(session)
    values = await repo.distribution(date_from=date_from, date_to=date_to)
    if not values:
        return DistributionResponse(
            mean=_ZERO, median=_ZERO, p90=_ZERO, min=_ZERO, max=_ZERO, count=0
        )
    values_sorted = sorted(values)
    count = len(values_sorted)
    mean = (sum(values_sorted, _ZERO) / count).quantize(_ZERO)
    median = (
        values_sorted[count // 2]
        if count % 2 == 1
        else ((values_sorted[count // 2 - 1] + values_sorted[count // 2]) / 2).quantize(_ZERO)
    )
    p90_index = min(count - 1, max(0, math.ceil(count * 0.9) - 1))
    return DistributionResponse(
        mean=mean,
        median=median,
        p90=values_sorted[p90_index],
        min=values_sorted[0],
        max=values_sorted[-1],
        count=count,
    )


@router.get("/importance-trend", response_model=ImportanceTrendResponse)
async def importance_trend(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> ImportanceTrendResponse:
    repo = AnalyticsRepository(session)
    months, series = await repo.importance_trend(date_from=date_from, date_to=date_to)
    return ImportanceTrendResponse(
        months=months,
        series=[
            ImportanceTrendSeriesOut(
                importance=s.importance,  # type: ignore[arg-type]
                total=s.total,
                points=[ImportanceTrendPointOut(month=p.month, total=p.total) for p in s.points],
            )
            for s in series
        ],
    )


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def summary(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    as_of: AsOf = None,
) -> AnalyticsSummaryResponse:
    repo = AnalyticsRepository(session)
    months = await repo.monthly_totals(date_from=date_from, date_to=date_to)
    trends = await repo.category_trends(date_from=date_from, date_to=date_to)

    total = sum((m.total for m in months), _ZERO)
    transaction_count = sum(m.count for m in months)
    months_covered = len(months)
    average_per_month = (total / months_covered).quantize(_ZERO) if months_covered else _ZERO
    if as_of is not None:
        validate_iso_date(as_of)
    current_month = as_of[:7] if as_of is not None else None
    complete_months = [m for m in months if m.month != current_month] if current_month else months
    complete_months_covered = len(complete_months)
    complete_total = sum((m.total for m in complete_months), _ZERO)
    average_per_complete_month = (
        (complete_total / complete_months_covered).quantize(_ZERO)
        if complete_months_covered
        else _ZERO
    )
    average_per_transaction = (
        (total / transaction_count).quantize(_ZERO) if transaction_count else _ZERO
    )

    busiest = max(months, key=lambda m: m.total, default=None)
    top_category = trends[0] if trends else None

    # Month-over-month: latest complete month vs the prior one.
    mom_months = complete_months if as_of is not None else months
    latest = mom_months[-1] if mom_months else None
    previous = mom_months[-2] if len(mom_months) >= 2 else None
    latest_total = latest.total if latest else _ZERO
    previous_total = previous.total if previous else _ZERO
    current_month_row = (
        next((m for m in months if m.month == current_month), None) if current_month else None
    )
    current_month_to_date = current_month_row.total if current_month_row else _ZERO
    current_month_projected = _ZERO
    current_month_pace_vs_average = None
    if as_of is not None and current_month and current_month_row is not None:
        day_of_month = int(validate_iso_date(as_of)[8:10])
        projected = current_month_to_date / day_of_month * Decimal(str(_month_days(current_month)))
        current_month_projected = projected.quantize(_ZERO)
        current_month_pace_vs_average = _percent_change(
            current_month_projected, average_per_complete_month
        )

    return AnalyticsSummaryResponse(
        total=total,
        transaction_count=transaction_count,
        months_covered=months_covered,
        average_per_month=average_per_month,
        complete_months_covered=complete_months_covered,
        average_per_complete_month=average_per_complete_month,
        average_per_transaction=average_per_transaction,
        busiest_month=busiest.month if busiest else None,
        busiest_month_total=busiest.total if busiest else _ZERO,
        current_month=current_month,
        current_month_to_date=current_month_to_date,
        current_month_projected=current_month_projected,
        current_month_pace_vs_average=current_month_pace_vs_average,
        top_category_id=top_category.category_id if top_category else None,
        top_category_name=top_category.category_name if top_category else None,
        top_category_total=top_category.total if top_category else _ZERO,
        latest_month=latest.month if latest else None,
        latest_month_total=latest_total,
        previous_month_total=previous_total,
        month_over_month_delta=latest_total - previous_total,
        month_over_month_percent=_percent_change(latest_total, previous_total),
    )


@router.get("/diagnosis", response_model=DiagnosisResponse)
async def diagnosis(
    session: SessionDep,
    as_of: Annotated[str, Query(alias="as_of")],
) -> DiagnosisResponse:
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of=as_of)
    return DiagnosisResponse(
        latest_month=result.latest_month,
        baseline_from=result.baseline_from,
        baseline_to=result.baseline_to,
        baseline_month_count=result.baseline_month_count,
        total_current=result.total_current,
        total_baseline=result.total_baseline,
        increases=[
            DiagnosisIncreaseOut(
                category_id=c.category_id,
                category_name=c.category_name,
                color=c.color,
                current=c.current,
                baseline=c.baseline,
                delta=c.delta,
                percent_change=c.percent_change,
                is_new=c.is_new,
                contributors=[
                    DiagnosisContributorOut(
                        merchant=m.merchant,
                        current=m.current,
                        baseline=m.baseline,
                        delta=m.delta,
                        is_new=m.is_new,
                    )
                    for m in c.contributors
                ],
                transactions=[
                    DiagnosisTransactionOut(
                        id=t.id,
                        name=t.name,
                        display_name=t.display_name,
                        amount=t.amount,
                        date=t.date,
                    )
                    for t in c.transactions
                ],
            )
            for c in result.increases
        ],
        other_increases_total=result.other_increases_total,
        other_increases_count=result.other_increases_count,
        decreases=[
            DiagnosisDecreaseOut(
                category_id=d.category_id,
                category_name=d.category_name,
                color=d.color,
                current=d.current,
                baseline=d.baseline,
                delta=d.delta,
            )
            for d in result.decreases
        ],
    )
