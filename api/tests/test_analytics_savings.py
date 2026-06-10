"""Repository-level tests for AnalyticsRepository.savings."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from quid_api.models import Category, Expense
from quid_api.repositories.analytics import AnalyticsRepository
from tests.conftest import make_category, make_expense

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess


async def _seed(session, name: str, amount: str, date: str) -> None:
    session.add(
        Expense(
            id=f"e-{name}-{date}-{amount}",
            name=name,
            amount=Decimal(amount),
            date=date,
            category_id="c1",
            note="",
            importance="important",
            category_source="import",
        )
    )


# Explicit (NOT autouse): the endpoint tests below must not pull in the
# file-local `session` fixture, or its open write transaction would deadlock
# the app_client's separate connections on the same per-test SQLite file.
@pytest_asyncio.fixture
async def category(session):
    session.add(Category(id="c1", name="Subs", color="#888888", icon="tag", description=""))
    await session.flush()


async def test_savings_empty_db(session, category):
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert result.latest_month is None
    assert result.price_creep == []
    assert result.stack_monthly_total == Decimal("0.00")


async def test_price_creep_detected(session, category):
    # Netflix at 10.99 for 4 months, then 12.99 for 3 consecutive months.
    for month in ("2025-11", "2025-12", "2026-01", "2026-02"):
        await _seed(session, "Netflix", "10.99", f"{month}-05")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _seed(session, "Netflix", "12.99", f"{month}-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert len(result.price_creep) == 1
    item = result.price_creep[0]
    assert item.name == "Netflix"
    assert item.old_amount == Decimal("10.99")
    assert item.new_amount == Decimal("12.99")
    assert item.monthly_delta == Decimal("2.00")
    assert item.annual_delta == Decimal("24.00")
    assert item.since_month == "2026-03"


async def test_price_creep_requires_consecutive_new_months(session, category):
    # New amount appears in two NON-consecutive months -> not creep.
    for month in ("2025-11", "2025-12", "2026-01"):
        await _seed(session, "Gym", "32.00", f"{month}-05")
    await _seed(session, "Gym", "35.00", "2026-03-05")
    await _seed(session, "Gym", "35.00", "2026-05-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert result.price_creep == []


async def test_new_recurring_detected_and_creep_not_double_reported(session, category):
    # iCloud: first-ever in March, recurring 3 months -> NEW.
    for month in ("2026-03", "2026-04", "2026-05"):
        await _seed(session, "iCloud", "2.99", f"{month}-05")
    # Netflix creep (first-ever long ago) must NOT appear as new recurring.
    for month in ("2025-11", "2025-12", "2026-01"):
        await _seed(session, "Netflix", "10.99", f"{month}-05")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _seed(session, "Netflix", "12.99", f"{month}-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert [n.name for n in result.new_recurring] == ["iCloud"]
    assert result.new_recurring[0].annual_cost == Decimal("35.88")
    assert result.new_recurring[0].first_month == "2026-03"


async def test_habit_spend(session, category):
    # 7 small Pret visits in the latest complete month (2026-05).
    for day in range(2, 9):
        await _seed(session, "Pret", "3.50", f"2026-05-0{day}")
    # High-ticket frequent merchant is NOT a habit (avg > 20).
    for day in range(10, 17):
        await _seed(session, "Fancy Restaurant", "45.00", f"2026-05-{day}")
    # Frequent merchant in an OLDER month doesn't count.
    for day in range(2, 9):
        await _seed(session, "Costa", "3.00", f"2026-04-0{day}")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert [h.name for h in result.habits] == ["Pret"]
    habit = result.habits[0]
    assert habit.count == 7
    assert habit.total == Decimal("24.50")
    assert habit.average == Decimal("3.50")


async def test_recurring_stack_active_and_estimate_scaling(session, category):
    # Monthly active sub: estimate = amount.
    for month in ("2026-02", "2026-03", "2026-04", "2026-05"):
        await _seed(session, "Spotify", "9.99", f"{month}-05")
    # Quarterly bill: 3 charges spanning 7 months -> estimate scaled by 3/7.
    for month in ("2025-11", "2026-02", "2026-05"):
        await _seed(session, "Water Co", "90.00", f"{month}-05")
    # Cancelled sub (last seen 3 months before latest): excluded.
    for month in ("2025-11", "2025-12", "2026-01", "2026-02"):
        await _seed(session, "Old Mag", "5.00", f"{month}-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    names = [s.name for s in result.stack_items]
    assert "Spotify" in names
    assert "Water Co" in names
    assert "Old Mag" not in names
    water = next(s for s in result.stack_items if s.name == "Water Co")
    # 90 * 3 / 7 = 38.57
    assert water.monthly_estimate == Decimal("38.57")
    spotify = next(s for s in result.stack_items if s.name == "Spotify")
    assert spotify.monthly_estimate == Decimal("9.99")
    assert result.stack_monthly_total == Decimal("48.56")
    assert result.stack_annual_total == Decimal("582.72")


async def test_savings_endpoint_shape(app_client: AsyncClient):
    cat = await make_category(app_client, "Subscriptions")
    for month in ("2026-03", "2026-04", "2026-05"):
        await make_expense(
            app_client, name="iCloud", amount="2.99", date=f"{month}-05", category_id=cat["id"]
        )
    res = await app_client.get("/api/v1/analytics/savings", params={"as_of": "2026-06-10"})
    assert res.status_code == 200
    body = res.json()
    assert body["latestMonth"] == "2026-05"
    assert body["priceCreep"] == []
    assert body["newRecurring"][0]["name"] == "iCloud"
    assert body["newRecurring"][0]["annualCost"] == "35.88"
    assert body["recurringStack"]["monthlyTotal"] == "2.99"
    assert body["recurringStack"]["items"][0]["monthlyEstimate"] == "2.99"
    assert body["habits"] == []


async def test_savings_endpoint_bad_as_of(app_client):
    res = await app_client.get("/api/v1/analytics/savings", params={"as_of": "junk"})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"
