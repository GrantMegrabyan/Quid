"""Repository-level tests for AnalyticsRepository.diagnosis."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

if TYPE_CHECKING:
    from httpx import AsyncClient

from quid_api.models import Category, Expense
from quid_api.repositories.analytics import AnalyticsRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess


async def _seed(session, category_id: str, name: str, amount: str, date: str) -> None:
    session.add(
        Expense(
            id=f"e-{category_id}-{name}-{date}-{amount}",
            name=name,
            amount=Decimal(amount),
            date=date,
            category_id=category_id,
            note="",
            importance="important",
            category_source="import",
        )
    )


async def _seed_cat(session, category_id: str, name: str) -> None:
    session.add(Category(id=category_id, name=name, color="#22c55e", icon="tag", description=""))


async def test_diagnosis_empty_db(session):
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.latest_month is None
    assert result.increases == []
    assert result.baseline_month_count == 0


async def test_diagnosis_single_complete_month_has_no_baseline(session):
    await _seed_cat(session, "c1", "Groceries")
    await _seed(session, "c1", "Tesco", "50.00", "2026-05-10")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.latest_month == "2026-05"
    assert result.baseline_month_count == 0
    assert result.increases == []
    assert result.total_current == Decimal("50.00")


async def test_diagnosis_zero_months_count_in_baseline(session):
    # Groceries spends 60 in Feb only; baseline window Feb..Apr (3 months,
    # clipped to first data month) -> baseline avg 20, not 60.
    await _seed_cat(session, "c1", "Groceries")
    await _seed(session, "c1", "Tesco", "60.00", "2026-02-10")
    await _seed(session, "c1", "Tesco", "90.00", "2026-05-10")
    # Another category keeps Mar/Apr present in the data (months exist).
    await _seed_cat(session, "c2", "Transport")
    await _seed(session, "c2", "TfL", "10.00", "2026-03-05")
    await _seed(session, "c2", "TfL", "10.00", "2026-04-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.latest_month == "2026-05"
    assert result.baseline_from == "2026-02"
    assert result.baseline_to == "2026-04"
    assert result.baseline_month_count == 3
    groceries = next(c for c in result.increases if c.category_name == "Groceries")
    assert groceries.baseline == Decimal("20.00")
    assert groceries.delta == Decimal("70.00")


async def test_diagnosis_baseline_capped_at_six_months(session):
    await _seed_cat(session, "c1", "Groceries")
    # 8 months of history before the latest complete month (2026-05):
    # 2025-09 .. 2026-04 at 10/mo; only the last 6 (2025-11..2026-04) count.
    for month in (
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ):
        await _seed(session, "c1", "Tesco", "10.00", f"{month}-15")
    await _seed(session, "c1", "Tesco", "40.00", "2026-05-15")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.baseline_from == "2025-11"
    assert result.baseline_to == "2026-04"
    assert result.baseline_month_count == 6
    groceries = result.increases[0]
    assert groceries.baseline == Decimal("10.00")
    assert groceries.delta == Decimal("30.00")


async def test_diagnosis_noise_floor_and_decreases(session):
    await _seed_cat(session, "c1", "Groceries")  # big increase: kept
    await _seed_cat(session, "c2", "Snacks")  # +5 on 100 (=5%): rolled up
    await _seed_cat(session, "c3", "Transport")  # decrease
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "50.00", f"{month}-10")
        await _seed(session, "c2", "Corner Shop", "100.00", f"{month}-11")
        await _seed(session, "c3", "TfL", "30.00", f"{month}-12")
    await _seed(session, "c1", "Tesco", "120.00", "2026-05-10")
    await _seed(session, "c2", "Corner Shop", "105.00", "2026-05-11")
    # Transport absent in May -> decrease of 30.
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert [c.category_name for c in result.increases] == ["Groceries"]
    assert result.other_increases_count == 1
    assert result.other_increases_total == Decimal("5.00")
    assert len(result.decreases) == 1
    assert result.decreases[0].category_name == "Transport"
    assert result.decreases[0].delta == Decimal("-30.00")


async def test_diagnosis_new_category_and_small_new_category(session):
    await _seed_cat(session, "c0", "Anchor")  # keeps baseline months populated
    await _seed_cat(session, "c1", "Hobbies")  # new, >=10 -> kept, is_new
    await _seed_cat(session, "c2", "Stationery")  # new, <10 -> rolled up
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c0", "Anchor Shop", "20.00", f"{month}-10")
    await _seed(session, "c1", "Hobby Store", "45.00", "2026-05-10")
    await _seed(session, "c2", "Paper Co", "4.00", "2026-05-11")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    hobbies = next(c for c in result.increases if c.category_name == "Hobbies")
    assert hobbies.is_new is True
    assert hobbies.percent_change is None
    assert hobbies.baseline == Decimal("0.00")
    assert all(c.category_name != "Stationery" for c in result.increases)
    assert result.other_increases_count == 1


async def test_diagnosis_contributors_and_transactions(session):
    await _seed_cat(session, "c1", "Groceries")
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "50.00", f"{month}-10")
    await _seed(session, "c1", "Tesco", "60.00", "2026-05-10")
    await _seed(session, "c1", "Waitrose", "70.00", "2026-05-12")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    groceries = result.increases[0]
    # Contributors sorted by merchant delta desc: Waitrose (new, +70) then
    # Tesco (60 vs 50 avg = +10).
    assert [c.merchant for c in groceries.contributors] == ["Waitrose", "Tesco"]
    assert groceries.contributors[0].is_new is True
    assert groceries.contributors[0].delta == Decimal("70.00")
    assert groceries.contributors[1].is_new is False
    assert groceries.contributors[1].delta == Decimal("10.00")
    # Transactions: the latest month's rows, largest first.
    assert [t.name for t in groceries.transactions] == ["Waitrose", "Tesco"]
    assert groceries.transactions[0].amount == Decimal("70.00")


async def test_diagnosis_overall_totals(session):
    await _seed_cat(session, "c1", "Groceries")
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "50.00", f"{month}-10")
    await _seed(session, "c1", "Tesco", "80.00", "2026-05-10")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.total_current == Decimal("80.00")
    assert result.total_baseline == Decimal("50.00")


async def _make_cat(client: AsyncClient, name: str) -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    assert res.status_code == 201
    return res.json()  # type: ignore[no-any-return]


async def _make_expense(
    client: AsyncClient, *, name: str, amount: str, date: str, category_id: str
) -> dict[str, Any]:
    res = await client.post(
        "/api/v1/expenses",
        json={"name": name, "amount": amount, "date": date, "categoryId": category_id},
    )
    assert res.status_code == 201, res.text
    return res.json()  # type: ignore[no-any-return]


async def test_diagnosis_endpoint_shape(app_client):
    cat = await _make_cat(app_client, "Groceries")
    for month in ("2026-03", "2026-04"):
        await _make_expense(
            app_client, name="Tesco", amount="50.00", date=f"{month}-10", category_id=cat["id"]
        )
    await _make_expense(
        app_client, name="Waitrose", amount="120.00", date="2026-05-10", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/diagnosis", params={"as_of": "2026-06-10"})
    assert res.status_code == 200
    body = res.json()
    assert body["latestMonth"] == "2026-05"
    assert body["baselineMonthCount"] == 2
    assert body["totalCurrent"] == "120.00"
    assert body["totalBaseline"] == "50.00"
    increase = body["increases"][0]
    assert increase["categoryName"] == "Groceries"
    assert increase["delta"] == "70.00"
    assert increase["isNew"] is False
    assert increase["contributors"][0]["merchant"] == "Waitrose"
    assert increase["contributors"][0]["isNew"] is True
    assert increase["transactions"][0]["amount"] == "120.00"
    assert body["decreases"] == []


async def test_diagnosis_endpoint_bad_as_of(app_client):
    res = await app_client.get("/api/v1/analytics/diagnosis", params={"as_of": "junk"})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"
