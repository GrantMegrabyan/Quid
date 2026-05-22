from __future__ import annotations


async def test_bulk_create_minimal(app_client):
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "Coffee",
                    "category": "eating_out",
                    "amount": -3.50,
                    "date": "2026-04-01",
                    "note": "",
                }
            ]
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 1
    assert body["categoriesCreated"][0]["id"] == "cat-eating-out"
    assert body["categoriesCreated"][0]["name"] == "Eating Out"
    assert body["expenses"][0]["amount"] == 3.5


async def test_bulk_create_uses_existing_category_by_name(app_client):
    await app_client.post(
        "/api/v1/categories",
        json={"name": "Groceries", "icon": "shopping-cart"},
    )
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {"name": "Whole Foods", "category": "groceries", "amount": 1.0, "date": "2026-04-01", "note": ""}
            ]
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["categoriesCreated"] == []
    cats = (await app_client.get("/api/v1/categories")).json()
    assert sum(1 for c in cats if c["name"].lower() == "groceries") == 1


async def test_bulk_create_other_maps_to_uncategorized(app_client):
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {"name": "X", "category": "other", "amount": 5.0, "date": "2026-04-01", "note": ""}
            ]
        },
    )
    assert res.status_code == 201
    assert res.json()["expenses"][0]["categoryId"] == "uncategorized"
    assert res.json()["categoriesCreated"] == []


async def test_bulk_create_rolls_back_on_bad_row(app_client):
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {"name": "ok", "category": "groceries", "amount": 1.0, "date": "2026-04-01", "note": ""},
                {"name": "bad", "category": "groceries", "amount": 0, "date": "2026-04-01", "note": ""},
            ]
        },
    )
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION"
    assert "row 1" in body["message"]

    after = (await app_client.get("/api/v1/expenses")).json()
    assert after == []


async def test_bulk_create_abs_negative_amount(app_client):
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {"name": "X", "category": "bills", "amount": -42.42, "date": "2026-04-01", "note": ""}
            ]
        },
    )
    assert res.status_code == 201
    assert res.json()["expenses"][0]["amount"] == 42.42


async def test_bulk_create_rejects_empty_items(app_client):
    res = await app_client.post("/api/v1/expenses/bulk", json={"items": []})
    assert res.status_code == 422


async def test_bulk_create_rejects_oversize_payload(app_client):
    items = [
        {"name": "X", "category": "groceries", "amount": 1.0, "date": "2026-04-01", "note": ""}
        for _ in range(5001)
    ]
    res = await app_client.post("/api/v1/expenses/bulk", json={"items": items})
    assert res.status_code == 422


async def test_bulk_create_full_csv_shape_three_files(app_client):
    monzo = [
        {"name": "Transport for London", "category": "transport", "amount": -1.75, "date": "2026-04-01", "note": ""},
        {"name": "Tesco", "category": "groceries", "amount": -42.31, "date": "2026-04-02", "note": ""},
    ]
    revolut = [
        {"name": "Starbucks", "category": "eating_out", "amount": 10.00, "date": "2026-04-01", "note": ""},
        {"name": "Uber", "category": "transport", "amount": 19.98, "date": "2026-04-01", "note": ""},
    ]
    shared = [
        {"name": "One Utility Bill", "category": "bills", "amount": -269.23, "date": "2026-04-01", "note": ""},
    ]
    total = monzo + revolut + shared
    res = await app_client.post("/api/v1/expenses/bulk", json={"items": total})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 5
    new_cat_names = {c["name"].lower() for c in body["categoriesCreated"]}
    assert {"transport", "groceries", "eating out", "bills"}.issubset(new_cat_names)
    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert all(e["amount"] > 0 for e in expenses)
