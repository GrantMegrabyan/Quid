from __future__ import annotations


async def test_get_returns_default_singleton(app_client):
    res = await app_client.get("/api/v1/settings")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["currency"] == "GBP"
    assert body["showImportanceBadge"] is True
    assert "updatedAt" in body


async def test_patch_updates_currency(app_client):
    res = await app_client.patch("/api/v1/settings", json={"currency": "usd"})
    assert res.status_code == 200, res.text
    assert res.json()["currency"] == "USD"

    again = await app_client.get("/api/v1/settings")
    assert again.json()["currency"] == "USD"


async def test_patch_updates_badge_toggle(app_client):
    res = await app_client.patch("/api/v1/settings", json={"showImportanceBadge": False})
    assert res.status_code == 200, res.text
    assert res.json()["showImportanceBadge"] is False

    flipped = await app_client.patch("/api/v1/settings", json={"showImportanceBadge": True})
    assert flipped.json()["showImportanceBadge"] is True


async def test_patch_rejects_invalid_currency_length(app_client):
    short = await app_client.patch("/api/v1/settings", json={"currency": "GB"})
    assert short.status_code == 422
    long = await app_client.patch("/api/v1/settings", json={"currency": "EURO"})
    assert long.status_code == 422


async def test_patch_rejects_non_alpha_currency(app_client):
    res = await app_client.patch("/api/v1/settings", json={"currency": "12$"})
    assert res.status_code == 422
