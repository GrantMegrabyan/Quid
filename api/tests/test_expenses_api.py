from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _make_cat(client: AsyncClient, name: str = "Food") -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    return res.json()  # type: ignore[no-any-return]


async def test_list_empty(app_client):
    res = await app_client.get("/api/v1/expenses")
    assert res.status_code == 200
    assert res.json() == []


async def test_create_and_get(app_client):
    cat = await _make_cat(app_client)
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Coffee",
            "amount": "4.50",
            "date": "2026-05-22",
            "categoryId": cat["id"],
            "note": "morning",
        },
    )
    assert res.status_code == 201
    exp = res.json()
    assert exp["amount"] == "4.50"
    assert isinstance(exp["amount"], str)

    fetched = await app_client.get(f"/api/v1/expenses/{exp['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == exp["id"]


async def test_create_rejects_negative_amount(app_client):
    cat = await _make_cat(app_client)
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Bad",
            "amount": "-5",
            "date": "2026-05-22",
            "categoryId": cat["id"],
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"


async def test_create_rejects_bad_date(app_client):
    cat = await _make_cat(app_client)
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Bad",
            "amount": "5",
            "date": "22/05/2026",
            "categoryId": cat["id"],
        },
    )
    assert res.status_code == 422


async def test_create_rejects_unknown_category(app_client):
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Bad",
            "amount": "5",
            "date": "2026-05-22",
            "categoryId": "cat-nope",
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"


async def test_list_sorts_by_date_desc(app_client):
    cat = await _make_cat(app_client)
    for d in ("2026-01-01", "2026-03-01", "2026-02-01"):
        await app_client.post(
            "/api/v1/expenses",
            json={"name": d, "amount": "1", "date": d, "categoryId": cat["id"]},
        )
    res = await app_client.get("/api/v1/expenses")
    dates = [e["date"] for e in res.json()]
    assert dates == ["2026-03-01", "2026-02-01", "2026-01-01"]


async def test_list_pagination(app_client):
    cat = await _make_cat(app_client)
    for d in ("2026-01-01", "2026-02-01", "2026-03-01"):
        await app_client.post(
            "/api/v1/expenses",
            json={"name": d, "amount": "1", "date": d, "categoryId": cat["id"]},
        )
    res = await app_client.get("/api/v1/expenses?limit=1&offset=1")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["date"] == "2026-02-01"


async def test_patch_partial(app_client):
    cat = await _make_cat(app_client)
    cat2 = await _make_cat(app_client, name="Travel")
    created = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "A",
            "amount": "10",
            "date": "2026-01-01",
            "categoryId": cat["id"],
            "note": "hi",
        },
    )
    exp_id = created.json()["id"]
    res = await app_client.patch(
        f"/api/v1/expenses/{exp_id}",
        json={"categoryId": cat2["id"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["categoryId"] == cat2["id"]
    assert body["name"] == "A"
    assert body["amount"] == "10.00"


async def test_delete(app_client):
    cat = await _make_cat(app_client)
    created = await app_client.post(
        "/api/v1/expenses",
        json={"name": "A", "amount": "1", "date": "2026-01-01", "categoryId": cat["id"]},
    )
    exp_id = created.json()["id"]
    res = await app_client.delete(f"/api/v1/expenses/{exp_id}")
    assert res.status_code == 204

    follow = await app_client.get(f"/api/v1/expenses/{exp_id}")
    assert follow.status_code == 404


async def test_cascade_delete_via_http(app_client):
    target = await _make_cat(app_client, name="Travel")
    other = await _make_cat(app_client, name="Bills")
    e1 = (
        await app_client.post(
            "/api/v1/expenses",
            json={"name": "h", "amount": "10", "date": "2026-01-01", "categoryId": target["id"]},
        )
    ).json()
    e2 = (
        await app_client.post(
            "/api/v1/expenses",
            json={"name": "k", "amount": "20", "date": "2026-01-02", "categoryId": other["id"]},
        )
    ).json()

    res = await app_client.delete(f"/api/v1/categories/{target['id']}")
    assert res.status_code == 204

    e1_after = (await app_client.get(f"/api/v1/expenses/{e1['id']}")).json()
    e2_after = (await app_client.get(f"/api/v1/expenses/{e2['id']}")).json()
    assert e1_after["categoryId"] == "uncategorized"
    assert e2_after["categoryId"] == other["id"]


async def test_cors_preflight(app_client):
    res = await app_client.options(
        "/api/v1/categories",
        headers={
            "Origin": "http://localhost:61234",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:61234"
