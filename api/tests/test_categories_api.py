from __future__ import annotations


async def test_list_initial_state(app_client):
    res = await app_client.get("/api/v1/categories")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert [c["id"] for c in body] == ["uncategorized"]
    cat = body[0]
    assert cat["name"] == "Uncategorized"
    assert "color" in cat
    assert "icon" in cat
    assert "description" in cat


async def test_get_uncategorized(app_client):
    res = await app_client.get("/api/v1/categories/uncategorized")
    assert res.status_code == 200
    assert res.json()["id"] == "uncategorized"


async def test_get_missing_returns_404_with_error_body(app_client):
    res = await app_client.get("/api/v1/categories/cat-nope")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert "cat-nope" in body["message"]


async def test_create_category(app_client):
    res = await app_client.post(
        "/api/v1/categories",
        json={"name": "Groceries", "icon": "shopping-cart"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Groceries"
    assert body["icon"] == "shopping-cart"
    assert body["description"] == ""
    assert body["id"].startswith("cat-")
    assert body["color"].startswith("#")


async def test_category_icon_round_trips_new_lucide_key(app_client):
    created = await app_client.post(
        "/api/v1/categories",
        json={"name": "Tickets", "icon": "ticket"},
    )
    assert created.status_code == 201
    cat_id = created.json()["id"]
    assert created.json()["icon"] == "ticket"

    updated = await app_client.patch(
        f"/api/v1/categories/{cat_id}", json={"icon": "car-taxi-front"}
    )
    assert updated.status_code == 200
    assert updated.json()["icon"] == "car-taxi-front"

    fetched = await app_client.get(f"/api/v1/categories/{cat_id}")
    assert fetched.status_code == 200
    assert fetched.json()["icon"] == "car-taxi-front"


async def test_create_category_blank_name_returns_422(app_client):
    res = await app_client.post("/api/v1/categories", json={"name": ""})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION"


async def test_create_category_duplicate_name_returns_422(app_client):
    await app_client.post("/api/v1/categories", json={"name": "A"})
    res = await app_client.post("/api/v1/categories", json={"name": "a"})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION"
    assert "already exists" in body["message"]


async def test_patch_category_name(app_client):
    created = await app_client.post("/api/v1/categories", json={"name": "Old"})
    cat_id = created.json()["id"]
    res = await app_client.patch(f"/api/v1/categories/{cat_id}", json={"name": "New"})
    assert res.status_code == 200
    assert res.json()["name"] == "New"


async def test_patch_uncategorized_name_returns_409(app_client):
    res = await app_client.patch("/api/v1/categories/uncategorized", json={"name": "Misc"})
    assert res.status_code == 409
    assert res.json()["code"] == "IMMUTABLE"


async def test_patch_can_change_uncategorized_color(app_client):
    res = await app_client.patch("/api/v1/categories/uncategorized", json={"color": "#abcdef"})
    assert res.status_code == 200
    assert res.json()["color"] == "#abcdef"


async def test_delete_category(app_client):
    created = await app_client.post("/api/v1/categories", json={"name": "Temp"})
    cat_id = created.json()["id"]
    res = await app_client.delete(f"/api/v1/categories/{cat_id}")
    assert res.status_code == 204
    follow = await app_client.get(f"/api/v1/categories/{cat_id}")
    assert follow.status_code == 404


async def test_delete_uncategorized_returns_409(app_client):
    res = await app_client.delete("/api/v1/categories/uncategorized")
    assert res.status_code == 409
    assert res.json()["code"] == "IMMUTABLE"


async def test_delete_missing_returns_404(app_client):
    res = await app_client.delete("/api/v1/categories/cat-missing")
    assert res.status_code == 404


async def test_camelcase_field_in_payload_for_expense_works(app_client):
    cat = (await app_client.post("/api/v1/categories", json={"name": "Food"})).json()
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Test",
            "amount": "10.50",
            "date": "2026-05-22",
            "categoryId": cat["id"],
            "note": "",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["categoryId"] == cat["id"]
    assert "category_id" not in body
