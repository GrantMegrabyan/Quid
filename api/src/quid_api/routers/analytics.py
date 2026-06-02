"""Read-only analytics endpoints (aggregations over expenses).

Endpoints accept an optional ``date_from`` / ``date_to`` (inclusive,
``YYYY-MM-DD``) window. When omitted they cover all of history. The
``category-comparison`` endpoint instead takes two explicit periods so the UI
can ask "this month vs last month" or "this quarter vs last quarter".
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query

from quid_api.db import get_session
from quid_api.repositories.analytics import AnalyticsRepository
from quid_api.schemas import (
    AnalyticsSummaryResponse,
    CategoryComparisonResponse,
    CategoryMoverOut,
    CategoryTrendPointOut,
    CategoryTrendSeriesOut,
    CategoryTrendsResponse,
    ImportanceBreakdownPointOut,
    ImportanceBreakdownResponse,
    MonthlyTotalOut,
    MonthlyTotalsResponse,
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


def _percent_change(current: Decimal, previous: Decimal) -> float | None:
    """Percent change of ``current`` vs ``previous`` (e.g. 25.0 = +25%).

    ``None`` when there's no previous baseline (avoids a divide-by-zero / a
    misleading "infinite %" badge).
    """
    if previous == _ZERO:
        return None
    return float((current - previous) / previous * 100)


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
) -> CategoryTrendsResponse:
    repo = AnalyticsRepository(session)
    series = await repo.category_trends(date_from=date_from, date_to=date_to)

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


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def summary(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> AnalyticsSummaryResponse:
    repo = AnalyticsRepository(session)
    months = await repo.monthly_totals(date_from=date_from, date_to=date_to)
    trends = await repo.category_trends(date_from=date_from, date_to=date_to)

    total = sum((m.total for m in months), _ZERO)
    transaction_count = sum(m.count for m in months)
    months_covered = len(months)
    average_per_month = (total / months_covered).quantize(_ZERO) if months_covered else _ZERO
    average_per_transaction = (
        (total / transaction_count).quantize(_ZERO) if transaction_count else _ZERO
    )

    busiest = max(months, key=lambda m: m.total, default=None)
    top_category = trends[0] if trends else None

    # Month-over-month: the latest month in the window vs the prior one.
    latest = months[-1] if months else None
    previous = months[-2] if len(months) >= 2 else None
    latest_total = latest.total if latest else _ZERO
    previous_total = previous.total if previous else _ZERO

    return AnalyticsSummaryResponse(
        total=total,
        transaction_count=transaction_count,
        months_covered=months_covered,
        average_per_month=average_per_month,
        average_per_transaction=average_per_transaction,
        busiest_month=busiest.month if busiest else None,
        busiest_month_total=busiest.total if busiest else _ZERO,
        top_category_id=top_category.category_id if top_category else None,
        top_category_name=top_category.category_name if top_category else None,
        top_category_total=top_category.total if top_category else _ZERO,
        latest_month=latest.month if latest else None,
        latest_month_total=latest_total,
        previous_month_total=previous_total,
        month_over_month_delta=latest_total - previous_total,
        month_over_month_percent=_percent_change(latest_total, previous_total),
    )
