"""Analytics endpoints (aggregations over expenses).

Most endpoints are read-only aggregations. The one exception is
``POST /narrative``, which generates an AI summary via OpenRouter, persists
it to the ``analytics_narratives`` table, and returns it.

``summary`` and ``monthly-totals`` accept an optional ``date_from`` /
``date_to`` (inclusive, ``YYYY-MM-DD``) window; when omitted they cover all of
history. The insight endpoints (``diagnosis``, ``savings``, ``narrative``)
instead take a required ``as_of`` date and anchor their fixed windows on the
latest complete month before it.
"""

from __future__ import annotations

import calendar
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query

from quid_api.ai_narrative import generate_narrative as ai_generate_narrative
from quid_api.datelib import validate_iso_date
from quid_api.db import get_session
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.analytics import AnalyticsRepository
from quid_api.repositories.analytics_narrative import AnalyticsNarrativeRepository
from quid_api.schemas import (
    AnalyticsSummaryResponse,
    DiagnosisContributorOut,
    DiagnosisDecreaseOut,
    DiagnosisIncreaseOut,
    DiagnosisResponse,
    DiagnosisTransactionOut,
    HabitOut,
    MonthlyTotalOut,
    MonthlyTotalsResponse,
    NarrativeGenerateRequest,
    NarrativeOut,
    NarrativeResponse,
    NewRecurringOut,
    PriceCreepOut,
    RecurringStackItemOut,
    RecurringStackOut,
    SavingsResponse,
)
from quid_api.settings import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import AnalyticsNarrative

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_ZERO = Decimal("0.00")

DateFrom = Annotated[str | None, Query(alias="date_from")]
DateTo = Annotated[str | None, Query(alias="date_to")]
AsOf = Annotated[str | None, Query(alias="as_of")]


def _narrative_out(row: AnalyticsNarrative) -> NarrativeOut:
    return NarrativeOut(
        month=row.month,
        content=row.content,
        generated_at=row.generated_at,
        model=row.model,
    )


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


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def summary(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    as_of: AsOf = None,
) -> AnalyticsSummaryResponse:
    repo = AnalyticsRepository(session)
    months = await repo.monthly_totals(date_from=date_from, date_to=date_to)

    total = sum((m.total for m in months), _ZERO)
    transaction_count = sum(m.count for m in months)
    months_covered = len(months)
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

    latest = complete_months[-1] if complete_months else None
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
        complete_months_covered=complete_months_covered,
        average_per_complete_month=average_per_complete_month,
        latest_month=latest.month if latest else None,
        latest_month_total=latest.total if latest else _ZERO,
        current_month=current_month,
        current_month_to_date=current_month_to_date,
        current_month_projected=current_month_projected,
        current_month_pace_vs_average=current_month_pace_vs_average,
    )


@router.get("/savings", response_model=SavingsResponse)
async def savings(
    session: SessionDep,
    as_of: Annotated[str, Query(alias="as_of")],
) -> SavingsResponse:
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of=as_of)
    return SavingsResponse(
        latest_month=result.latest_month,
        window_from=result.window_from,
        price_creep=[
            PriceCreepOut(
                name=i.name,
                old_amount=i.old_amount,
                new_amount=i.new_amount,
                monthly_delta=i.monthly_delta,
                annual_delta=i.annual_delta,
                since_month=i.since_month,
            )
            for i in result.price_creep
        ],
        new_recurring=[
            NewRecurringOut(
                name=i.name, amount=i.amount, first_month=i.first_month, annual_cost=i.annual_cost
            )
            for i in result.new_recurring
        ],
        habits=[
            HabitOut(name=i.name, count=i.count, total=i.total, average=i.average)
            for i in result.habits
        ],
        recurring_stack=RecurringStackOut(
            items=[
                RecurringStackItemOut(
                    name=i.name,
                    amount=i.amount,
                    months_covered=i.months_covered,
                    first_month=i.first_month,
                    last_month=i.last_month,
                    monthly_estimate=i.monthly_estimate,
                )
                for i in result.stack_items
            ],
            monthly_total=result.stack_monthly_total,
            annual_total=result.stack_annual_total,
        ),
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


@router.get("/narrative", response_model=NarrativeResponse)
async def latest_narrative(session: SessionDep) -> NarrativeResponse:
    row = await AnalyticsNarrativeRepository(session).get_latest()
    return NarrativeResponse(narrative=None if row is None else _narrative_out(row))


@router.post("/narrative", response_model=NarrativeResponse)
async def generate_narrative(
    payload: NarrativeGenerateRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> NarrativeResponse:
    repo = AnalyticsRepository(session)
    diag = await repo.diagnosis(as_of=payload.as_of)
    if diag.latest_month is None:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Not enough data: at least one complete month is needed.",
        )
    sav = await repo.savings(as_of=payload.as_of)
    facts = {
        "month": diag.latest_month,
        "totalCurrent": str(diag.total_current),
        "totalBaseline": str(diag.total_baseline),
        "baselineMonths": diag.baseline_month_count,
        "increases": [
            {
                "category": c.category_name,
                "current": str(c.current),
                "baselineAvg": str(c.baseline),
                "delta": str(c.delta),
                "isNew": c.is_new,
                "topMerchants": [
                    {"name": m.merchant, "delta": str(m.delta), "isNew": m.is_new}
                    for m in c.contributors
                ],
            }
            for c in diag.increases[:6]
        ],
        "decreases": [
            {"category": d.category_name, "delta": str(d.delta)} for d in diag.decreases[:4]
        ],
        "priceCreep": [
            {
                "name": i.name,
                "oldAmount": str(i.old_amount),
                "newAmount": str(i.new_amount),
                "annualDelta": str(i.annual_delta),
            }
            for i in sav.price_creep
        ],
        "newRecurring": [
            {"name": i.name, "monthly": str(i.amount), "annualCost": str(i.annual_cost)}
            for i in sav.new_recurring
        ],
        "habits": [{"name": i.name, "visits": i.count, "total": str(i.total)} for i in sav.habits],
        "recurringStackMonthly": str(sav.stack_monthly_total),
    }
    content = await ai_generate_narrative(
        json.dumps(facts),
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
    )
    nrepo = AnalyticsNarrativeRepository(session)
    row = await nrepo.upsert(
        month=diag.latest_month, content=content, model=settings.openrouter_model
    )
    await session.commit()
    return NarrativeResponse(narrative=_narrative_out(row))
