"""The triage queue: labelling the merchants that carry the most spend."""

from __future__ import annotations

from tests.conftest import make_category, make_expense


async def _seed(client, merchants: list[tuple[str, str]]) -> str:
    cat = await make_category(client, "Groceries")
    for name, amount in merchants:
        await make_expense(
            client, name=name, amount=amount, date="2026-05-25", category_id=cat["id"]
        )
    return cat["id"]  # type: ignore[no-any-return]


async def test_queue_ranks_unlabelled_merchants_by_spend(app_client):
    await _seed(
        app_client,
        [("Tesco", "40.00"), ("Tesco", "60.00"), ("Netflix", "15.00"), ("Pret", "5.00")],
    )

    res = await app_client.get("/api/v1/importance/triage")
    assert res.status_code == 200, res.text
    body = res.json()
    assert [m["merchantName"] for m in body["merchants"]] == ["Tesco", "Netflix", "Pret"]
    tesco = body["merchants"][0]
    assert tesco["merchantKey"] == "tesco"
    assert tesco["transactionCount"] == 2
    assert tesco["totalAmount"] == "100.00"
    assert tesco["currentImportance"] == "important"


async def test_queue_honours_limit(app_client):
    await _seed(app_client, [("Tesco", "40.00"), ("Netflix", "15.00"), ("Pret", "5.00")])
    res = await app_client.get("/api/v1/importance/triage", params={"limit": 2})
    assert len(res.json()["merchants"]) == 2


async def test_labelling_a_merchant_removes_it_from_the_queue(app_client):
    await _seed(app_client, [("Tesco", "40.00"), ("Tesco", "60.00"), ("Netflix", "15.00")])

    res = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "tesco", "importance": "essential"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["updated"] == 2

    queue = await app_client.get("/api/v1/importance/triage")
    assert [m["merchantName"] for m in queue.json()["merchants"]] == ["Netflix"]

    expenses = await app_client.get("/api/v1/expenses")
    tesco = [e for e in expenses.json() if e["name"] == "Tesco"]
    assert all(e["importance"] == "essential" for e in tesco)
    assert all(e["importanceSource"] == "manual" for e in tesco)


async def test_triage_never_overwrites_a_per_transaction_decision(app_client):
    cat = await make_category(app_client, "Groceries")
    kept = await make_expense(
        app_client, name="Tesco", amount="40.00", date="2026-05-25", category_id=cat["id"]
    )
    await make_expense(
        app_client, name="Tesco", amount="60.00", date="2026-05-26", category_id=cat["id"]
    )
    await app_client.patch(f"/api/v1/expenses/{kept['id']}", json={"importance": "discretionary"})

    res = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "tesco", "importance": "essential"},
    )
    assert res.json()["updated"] == 1

    row = await app_client.get(f"/api/v1/expenses/{kept['id']}")
    assert row.json()["importance"] == "discretionary"


async def test_triage_matches_merchants_case_insensitively(app_client):
    await _seed(app_client, [("Tesco", "40.00"), ("TESCO ", "60.00")])
    res = await app_client.get("/api/v1/importance/triage")
    assert len(res.json()["merchants"]) == 1

    applied = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "TeSCo", "importance": "essential"},
    )
    assert applied.json()["updated"] == 2


async def test_coverage_tracks_labelled_spend_and_corrections(app_client):
    await _seed(app_client, [("Tesco", "40.00"), ("Netflix", "60.00")])

    before = (await app_client.get("/api/v1/importance/triage")).json()["coverage"]
    assert before["labelledMerchants"] == 0
    assert before["unlabelledMerchants"] == 2
    assert before["labelledAmount"] == "0.00"
    assert before["totalAmount"] == "100.00"
    assert before["corrections"] == 0

    res = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "tesco", "importance": "essential"},
    )
    coverage = res.json()["coverage"]
    assert coverage["labelledMerchants"] == 1
    assert coverage["labelledAmount"] == "40.00"
    # One correction, and it flipped the value, so it counts as an override.
    assert coverage["corrections"] == 1
    assert coverage["overrides"] == 1


async def test_confirming_the_current_value_is_logged_but_is_not_an_override(app_client):
    await _seed(app_client, [("Tesco", "40.00")])
    res = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "tesco", "importance": "important"},
    )
    coverage = res.json()["coverage"]
    assert res.json()["updated"] == 1
    assert coverage["corrections"] == 1
    assert coverage["overrides"] == 0
    assert coverage["labelledMerchants"] == 1


async def test_unknown_merchant_updates_nothing(app_client):
    await _seed(app_client, [("Tesco", "40.00")])
    res = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "nowhere", "importance": "essential"},
    )
    assert res.status_code == 200
    assert res.json()["updated"] == 0


async def test_invalid_importance_is_rejected(app_client):
    res = await app_client.post(
        "/api/v1/importance/triage",
        json={"merchantKey": "tesco", "importance": "critical"},
    )
    assert res.status_code == 422


async def test_empty_history_returns_an_empty_queue(app_client):
    res = await app_client.get("/api/v1/importance/triage")
    assert res.status_code == 200
    assert res.json()["merchants"] == []
    assert res.json()["coverage"]["totalAmount"] == "0.00"
