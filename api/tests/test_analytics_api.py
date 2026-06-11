from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _make_cat(client: AsyncClient, name: str) -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    assert res.status_code == 201
    return res.json()  # type: ignore[no-any-return]


async def _make_expense(
    client: AsyncClient,
    *,
    name: str,
    amount: str,
    date: str,
    category_id: str,
    importance: str = "important",
) -> dict[str, Any]:
    res = await client.post(
        "/api/v1/expenses",
        json={
            "name": name,
            "amount": amount,
            "date": date,
            "categoryId": category_id,
            "importance": importance,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()  # type: ignore[no-any-return]


# --------------------------------------------------------------------------- #
# monthly-totals                                                               #
# --------------------------------------------------------------------------- #


async def test_monthly_totals_empty(app_client):
    res = await app_client.get("/api/v1/analytics/monthly-totals")
    assert res.status_code == 200
    body = res.json()
    assert body["months"] == []
    assert body["total"] == "0.00"
    assert body["average"] == "0.00"
    assert body["count"] == 0


async def test_monthly_totals_groups_by_month(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="A", amount="10.00", date="2026-01-05", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="B", amount="20.00", date="2026-01-20", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="C", amount="30.00", date="2026-02-10", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/monthly-totals")
    assert res.status_code == 200
    body = res.json()
    assert body["months"] == [
        {"month": "2026-01", "total": "30.00", "count": 2},
        {"month": "2026-02", "total": "30.00", "count": 1},
    ]
    assert body["total"] == "60.00"
    assert body["average"] == "30.00"
    assert body["count"] == 3


async def test_monthly_totals_counts_timestamped_dates(app_client):
    cat = await _make_cat(app_client, "Food")
    # A timestamped date must still group under its YYYY-MM prefix.
    await _make_expense(
        app_client, name="Late", amount="5.00", date="2026-03-31T23:59:59", category_id=cat["id"]
    )
    res = await app_client.get("/api/v1/analytics/monthly-totals")
    body = res.json()
    assert body["months"] == [{"month": "2026-03", "total": "5.00", "count": 1}]


async def test_monthly_totals_window_filters_boundary_timestamp(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="Edge", amount="9.00", date="2026-04-30T23:59:59", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Next", amount="1.00", date="2026-05-01", category_id=cat["id"]
    )
    # Inclusive date_to of the 30th must keep the T23:59:59 row (exclusive upper).
    res = await app_client.get(
        "/api/v1/analytics/monthly-totals",
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
    )
    body = res.json()
    assert body["months"] == [{"month": "2026-04", "total": "9.00", "count": 1}]


# --------------------------------------------------------------------------- #
# summary                                                                      #
# --------------------------------------------------------------------------- #


async def test_summary_empty(app_client):
    res = await app_client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == "0.00"
    assert body["transactionCount"] == 0
    assert body["monthsCovered"] == 0
    assert body["completeMonthsCovered"] == 0
    assert body["averagePerCompleteMonth"] == "0.00"
    assert body["latestMonth"] is None
    assert body["currentMonth"] is None
    assert body["currentMonthPaceVsAverage"] is None


async def test_summary_headline_numbers(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="A", amount="10.00", date="2026-01-05", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="B", amount="20.00", date="2026-02-05", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="C", amount="100.00", date="2026-03-05", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/summary")
    body = res.json()
    assert body["total"] == "130.00"
    assert body["transactionCount"] == 3
    assert body["monthsCovered"] == 3
    # No as_of: every month counts as complete.
    assert body["completeMonthsCovered"] == 3
    assert body["averagePerCompleteMonth"] == "43.33"
    assert body["latestMonth"] == "2026-03"
    assert body["latestMonthTotal"] == "100.00"
    assert body["currentMonth"] is None
    assert body["currentMonthToDate"] == "0.00"


async def test_summary_as_of_uses_complete_month_baseline(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="Jan", amount="100.00", date="2026-01-01", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Feb", amount="200.00", date="2026-02-01", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="MTD", amount="30.00", date="2026-03-10", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/summary", params={"as_of": "2026-03-10"})
    body = res.json()
    assert body["completeMonthsCovered"] == 2
    assert body["averagePerCompleteMonth"] == "150.00"
    assert body["latestMonth"] == "2026-02"
    assert body["latestMonthTotal"] == "200.00"
    assert body["currentMonth"] == "2026-03"
    assert body["currentMonthToDate"] == "30.00"
    # Linear projection: 30 / 10 days * 31 days in March.
    assert body["currentMonthProjected"] == "93.00"
    # Pace vs the 150.00 complete-month average: (93 - 150) / 150 = -38%.
    assert body["currentMonthPaceVsAverage"] == -38.0


async def test_analytics_validates_bad_date(app_client):
    res = await app_client.get(
        "/api/v1/analytics/monthly-totals", params={"date_from": "2026-13-40"}
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"


async def test_summary_bad_as_of(app_client):
    res = await app_client.get("/api/v1/analytics/summary", params={"as_of": "junk"})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"


async def test_summary_as_of_no_current_month_data(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="Feb", amount="50.00", date="2026-02-10", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Mar", amount="80.00", date="2026-03-15", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/summary", params={"as_of": "2026-04-10"})
    assert res.status_code == 200
    body = res.json()
    assert body["currentMonth"] == "2026-04"
    assert body["currentMonthToDate"] == "0.00"
    assert body["currentMonthProjected"] == "0.00"
    assert body["currentMonthPaceVsAverage"] is None
    assert body["latestMonth"] == "2026-03"
