from __future__ import annotations


async def test_health(app_client):
    res = await app_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
