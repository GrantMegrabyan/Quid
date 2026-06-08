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
# category-trends                                                              #
# --------------------------------------------------------------------------- #


async def test_category_trends_dense_month_axis(app_client):
    food = await _make_cat(app_client, "Food")
    travel = await _make_cat(app_client, "Travel")
    await _make_expense(
        app_client, name="A", amount="10.00", date="2026-01-05", category_id=food["id"]
    )
    await _make_expense(
        app_client, name="B", amount="40.00", date="2026-02-05", category_id=food["id"]
    )
    await _make_expense(
        app_client, name="C", amount="25.00", date="2026-02-15", category_id=travel["id"]
    )

    res = await app_client.get("/api/v1/analytics/category-trends")
    assert res.status_code == 200
    body = res.json()
    assert body["months"] == ["2026-01", "2026-02"]
    # Series ordered by overall total desc: Food (50) before Travel (25).
    assert [s["categoryName"] for s in body["series"]] == ["Food", "Travel"]
    food_series = body["series"][0]
    assert food_series["total"] == "50.00"
    # Dense points: a zero-filled January for Food.
    assert food_series["points"] == [
        {"month": "2026-01", "total": "10.00"},
        {"month": "2026-02", "total": "40.00"},
    ]
    travel_series = body["series"][1]
    assert travel_series["points"] == [
        {"month": "2026-01", "total": "0.00"},
        {"month": "2026-02", "total": "25.00"},
    ]


async def test_category_trends_rolls_overflow_into_other(app_client):
    cat = await _make_cat(app_client, "Food")
    # Nine categories so the 8th limit forces an Other bucket.
    cats = [cat]
    for i in range(8):
        cats.append(await _make_cat(app_client, f"Cat{i}"))
    for i, c in enumerate(cats):
        await _make_expense(
            app_client,
            name=f"E{i}",
            amount=f"{10 * (i + 1)}.00",
            date="2026-01-05",
            category_id=c["id"],
        )
    res = await app_client.get("/api/v1/analytics/category-trends")
    body = res.json()
    assert body["series"][-1]["categoryId"] == "__other__"
    assert body["series"][-1]["categoryName"] == "Other"
    assert body["series"][-1]["color"] == "#6c7086"


# --------------------------------------------------------------------------- #
# recurring / large-transactions / distribution / importance-trend             #
# --------------------------------------------------------------------------- #


async def test_recurring_detects_three_month_groups(app_client):
    cat = await _make_cat(app_client, "Food")
    for month in ["2026-01", "2026-02", "2026-03"]:
        await _make_expense(
            app_client, name="Netflix", amount="12.00", date=f"{month}-05", category_id=cat["id"]
        )
    for month in ["2026-01", "2026-02"]:
        await _make_expense(
            app_client, name="Spotify", amount="8.00", date=f"{month}-05", category_id=cat["id"]
        )
    await _make_expense(
        app_client, name="Netflix", amount="13.00", date="2026-01-10", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/recurring")
    body = res.json()
    assert body["count"] == 1
    assert body["monthlyTotal"] == "12.00"
    item = body["items"][0]
    assert item["name"] == "Netflix"
    assert item["amount"] == "12.00"
    assert item["occurrences"] == 3
    assert item["monthsCovered"] == 3


async def test_recurring_same_name_two_amounts_are_distinct_items(app_client):
    # Same merchant at two different amounts, BOTH spanning >= 3 months and the
    # SAME first/last month. The detector groups on (name, amount), so this must
    # surface as TWO distinct recurring items sharing the name + firstMonth —
    # the shape that crashed the keyed each block in the UI (each_key_duplicate).
    cat = await _make_cat(app_client, "Food")
    for month in ["2026-01", "2026-02", "2026-03"]:
        await _make_expense(
            app_client, name="Apple", amount="0.99", date=f"{month}-05", category_id=cat["id"]
        )
        await _make_expense(
            app_client, name="Apple", amount="9.99", date=f"{month}-20", category_id=cat["id"]
        )

    res = await app_client.get("/api/v1/analytics/recurring")
    body = res.json()
    assert body["count"] == 2
    items = {item["amount"]: item for item in body["items"]}
    assert set(items) == {"0.99", "9.99"}
    # Both share the name and the same first/last month.
    assert {item["name"] for item in body["items"]} == {"Apple"}
    assert items["0.99"]["firstMonth"] == items["9.99"]["firstMonth"] == "2026-01"
    assert items["0.99"]["monthsCovered"] == items["9.99"]["monthsCovered"] == 3


async def test_large_transactions_returns_top_spend(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="Small", amount="10.00", date="2026-01-01", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Big", amount="100.00", date="2026-01-03", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Mid", amount="50.00", date="2026-01-02", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/large-transactions", params={"limit": 2})
    body = res.json()
    assert body["periodTotal"] == "160.00"
    assert body["topShare"] == 0.9375
    assert [t["name"] for t in body["transactions"]] == ["Big", "Mid"]


async def test_distribution_computes_percentiles(app_client):
    cat = await _make_cat(app_client, "Food")
    for idx, amount in enumerate(["10.00", "20.00", "30.00", "40.00", "1000.00"]):
        await _make_expense(
            app_client,
            name=f"T{idx}",
            amount=amount,
            date=f"2026-01-0{idx + 1}",
            category_id=cat["id"],
        )
    res = await app_client.get("/api/v1/analytics/distribution")
    body = res.json()
    assert body == {
        "mean": "220.00",
        "median": "30.00",
        "p90": "1000.00",
        "min": "10.00",
        "max": "1000.00",
        "count": 5,
    }


async def test_importance_trend_dense_axis(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client,
        name="A",
        amount="10.00",
        date="2026-01-01",
        category_id=cat["id"],
        importance="essential",
    )
    await _make_expense(
        app_client,
        name="B",
        amount="20.00",
        date="2026-02-01",
        category_id=cat["id"],
        importance="important",
    )
    res = await app_client.get("/api/v1/analytics/importance-trend")
    body = res.json()
    assert body["months"] == ["2026-01", "2026-02"]
    assert [s["importance"] for s in body["series"]] == ["essential", "important", "discretionary"]
    assert body["series"][0]["points"] == [
        {"month": "2026-01", "total": "10.00"},
        {"month": "2026-02", "total": "0.00"},
    ]


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


# --------------------------------------------------------------------------- #
# category-comparison                                                          #
# --------------------------------------------------------------------------- #


async def test_category_comparison_movers(app_client):
    food = await _make_cat(app_client, "Food")
    travel = await _make_cat(app_client, "Travel")
    # Previous period (Jan): Food 10, Travel 50.
    await _make_expense(
        app_client, name="P1", amount="10.00", date="2026-01-10", category_id=food["id"]
    )
    await _make_expense(
        app_client, name="P2", amount="50.00", date="2026-01-12", category_id=travel["id"]
    )
    # Current period (Feb): Food 40, Travel 0.
    await _make_expense(
        app_client, name="C1", amount="40.00", date="2026-02-10", category_id=food["id"]
    )

    res = await app_client.get(
        "/api/v1/analytics/category-comparison",
        params={
            "current_from": "2026-02-01",
            "current_to": "2026-02-28",
            "previous_from": "2026-01-01",
            "previous_to": "2026-01-31",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["currentTotal"] == "40.00"
    assert body["previousTotal"] == "60.00"
    movers = {m["categoryName"]: m for m in body["movers"]}
    # Food went up 10 -> 40 (+30, +300%).
    assert movers["Food"]["delta"] == "30.00"
    assert movers["Food"]["percentChange"] == 300.0
    # Travel went down 50 -> 0 (-50, -100%).
    assert movers["Travel"]["delta"] == "-50.00"
    assert movers["Travel"]["percentChange"] == -100.0


async def test_category_comparison_new_category_has_null_percent(app_client):
    food = await _make_cat(app_client, "Food")
    # Only present in the current period -> previous is zero -> percent None.
    await _make_expense(
        app_client, name="New", amount="15.00", date="2026-02-10", category_id=food["id"]
    )
    res = await app_client.get(
        "/api/v1/analytics/category-comparison",
        params={
            "current_from": "2026-02-01",
            "current_to": "2026-02-28",
            "previous_from": "2026-01-01",
            "previous_to": "2026-01-31",
        },
    )
    body = res.json()
    food_mover = next(m for m in body["movers"] if m["categoryName"] == "Food")
    assert food_mover["previous"] == "0.00"
    assert food_mover["percentChange"] is None


# --------------------------------------------------------------------------- #
# top-merchants                                                                #
# --------------------------------------------------------------------------- #


async def test_top_merchants_groups_case_insensitively(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client, name="Tesco", amount="10.00", date="2026-01-05", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="  tesco ", amount="5.00", date="2026-01-06", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Uber", amount="20.00", date="2026-01-07", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/top-merchants")
    assert res.status_code == 200
    body = res.json()
    merchants = body["merchants"]
    # Uber (20) first, then the merged Tesco (15, count 2).
    assert merchants[0]["merchant"] == "Uber"
    assert merchants[0]["total"] == "20.00"
    tesco = merchants[1]
    assert tesco["total"] == "15.00"
    assert tesco["count"] == 2


async def test_top_merchants_respects_limit(app_client):
    cat = await _make_cat(app_client, "Food")
    for i in range(5):
        await _make_expense(
            app_client, name=f"M{i}", amount=f"{i + 1}.00", date="2026-01-05", category_id=cat["id"]
        )
    res = await app_client.get("/api/v1/analytics/top-merchants", params={"limit": 2})
    body = res.json()
    assert len(body["merchants"]) == 2


# --------------------------------------------------------------------------- #
# importance-breakdown                                                         #
# --------------------------------------------------------------------------- #


async def test_importance_breakdown(app_client):
    cat = await _make_cat(app_client, "Food")
    await _make_expense(
        app_client,
        name="Rent",
        amount="100.00",
        date="2026-01-05",
        category_id=cat["id"],
        importance="essential",
    )
    await _make_expense(
        app_client,
        name="Toy",
        amount="30.00",
        date="2026-01-06",
        category_id=cat["id"],
        importance="discretionary",
    )
    res = await app_client.get("/api/v1/analytics/importance-breakdown")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == "130.00"
    by_imp = {b["importance"]: b for b in body["breakdown"]}
    assert by_imp["essential"]["total"] == "100.00"
    assert by_imp["discretionary"]["total"] == "30.00"


# --------------------------------------------------------------------------- #
# weekday-breakdown                                                            #
# --------------------------------------------------------------------------- #


async def test_weekday_breakdown_always_seven_days_monday_first(app_client):
    cat = await _make_cat(app_client, "Food")
    # 2026-01-05 is a Monday; 2026-01-11 is a Sunday.
    await _make_expense(
        app_client, name="Mon", amount="10.00", date="2026-01-05", category_id=cat["id"]
    )
    await _make_expense(
        app_client, name="Sun", amount="7.00", date="2026-01-11", category_id=cat["id"]
    )
    res = await app_client.get("/api/v1/analytics/weekday-breakdown")
    assert res.status_code == 200
    body = res.json()
    breakdown = body["breakdown"]
    assert len(breakdown) == 7
    assert breakdown[0]["weekday"] == 0  # Monday first
    assert breakdown[0]["total"] == "10.00"
    assert breakdown[6]["weekday"] == 6  # Sunday last
    assert breakdown[6]["total"] == "7.00"
    # A day with no spend is present with a zero total.
    assert breakdown[3]["total"] == "0.00"


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
    assert body["busiestMonth"] is None
    assert body["topCategoryId"] is None
    assert body["monthOverMonthPercent"] is None


async def test_summary_headline_kpis(app_client):
    food = await _make_cat(app_client, "Food")
    travel = await _make_cat(app_client, "Travel")
    await _make_expense(
        app_client, name="A", amount="10.00", date="2026-01-05", category_id=food["id"]
    )
    await _make_expense(
        app_client, name="B", amount="20.00", date="2026-02-05", category_id=food["id"]
    )
    await _make_expense(
        app_client, name="C", amount="100.00", date="2026-03-05", category_id=travel["id"]
    )

    res = await app_client.get("/api/v1/analytics/summary")
    body = res.json()
    assert body["total"] == "130.00"
    assert body["transactionCount"] == 3
    assert body["monthsCovered"] == 3
    assert body["busiestMonth"] == "2026-03"
    assert body["busiestMonthTotal"] == "100.00"
    # Travel (100) is the top category over the window.
    assert body["topCategoryName"] == "Travel"
    assert body["topCategoryTotal"] == "100.00"
    # MoM: March (100) vs Feb (20) -> +80, +400%.
    assert body["latestMonth"] == "2026-03"
    assert body["latestMonthTotal"] == "100.00"
    assert body["previousMonthTotal"] == "20.00"
    assert body["monthOverMonthDelta"] == "80.00"
    assert body["monthOverMonthPercent"] == 400.0


async def test_analytics_validates_bad_date(app_client):
    res = await app_client.get(
        "/api/v1/analytics/monthly-totals", params={"date_from": "2026-13-40"}
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"
