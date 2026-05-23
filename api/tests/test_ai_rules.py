from __future__ import annotations


async def test_ai_rules_seeded_and_crud(app_client):
    listed = await app_client.get("/api/v1/ai-rules")
    assert listed.status_code == 200
    rules = listed.json()
    assert [rule["text"] for rule in rules][:2] == [
        "Exclude transfers from categorisation/imports.",
        "If a purchase is fully refunded, exclude both the original purchase and the refund.",
    ]

    created = await app_client.post(
        "/api/v1/ai-rules",
        json={"text": "Exclude cash withdrawals.", "enabled": True, "priority": 20},
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["text"] == "Exclude cash withdrawals."

    updated = await app_client.patch(
        f"/api/v1/ai-rules/{rule['id']}",
        json={"enabled": False, "priority": 30},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["enabled"] is False
    assert updated.json()["priority"] == 30

    deleted = await app_client.delete(f"/api/v1/ai-rules/{rule['id']}")
    assert deleted.status_code == 204

    missing = await app_client.get(f"/api/v1/ai-rules/{rule['id']}")
    assert missing.status_code == 404


async def test_ai_rules_reject_blank_text(app_client):
    res = await app_client.post("/api/v1/ai-rules", json={"text": "   "})
    assert res.status_code == 422
