from __future__ import annotations

from dataclasses import replace
from typing import Any

from quid_api.ai_categorization import CategorizedBulkItems
from quid_api.ai_freeform import ParsedFreeformItem

RAW = "coffee 3.50 on 2026-04-01\nTesco 12.34 on 2026-04-01"


def _fake_parse(items: list[ParsedFreeformItem]):
    async def parser(text, *, api_key, model, **_: Any) -> list[ParsedFreeformItem]:
        return items

    return parser


async def test_freeform_preview_requires_text(app_client):
    resp = await app_client.post(
        "/api/v1/expenses/import-freeform/preview",
        json={"rawInput": "   "},
    )
    # Pydantic min_length=1 on the trimmed-less field still allows whitespace,
    # so the parser-level guard returns a 4xx validation error.
    assert resp.status_code in (400, 422), resp.text


async def test_freeform_preview_returns_review_rows(app_client, monkeypatch):
    monkeypatch.setattr(
        "quid_api.routers.expenses.parse_freeform_transactions",
        _fake_parse(
            [
                ParsedFreeformItem(name="Coffee", amount="3.50", date="2026-04-01", note=""),
                ParsedFreeformItem(name="Tesco", amount="12.34", date="2026-04-01", note=""),
            ]
        ),
    )

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        mapping = {"Coffee": "eating_out", "Tesco": "groceries"}
        return CategorizedBulkItems(
            items=[replace(item, category=mapping.get(item.name, "other")) for item in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})

    preview = await app_client.post(
        "/api/v1/expenses/import-freeform/preview",
        json={"rawInput": RAW},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"]["creates"] == 2
    assert body["summary"]["aiCategorized"] == 2
    assert len(body["rows"]) == 2
    names = {row["name"] for row in body["rows"]}
    assert names == {"Coffee", "Tesco"}
    for row in body["rows"]:
        assert row["filename"] == "AI free-form"
        assert row["kind"] == "create"


async def test_freeform_confirm_creates_and_logs_raw_input(app_client, monkeypatch):
    monkeypatch.setattr(
        "quid_api.routers.expenses.parse_freeform_transactions",
        _fake_parse([ParsedFreeformItem(name="Coffee", amount="3.50", date="2026-04-01", note="")]),
    )
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})

    preview = await app_client.post(
        "/api/v1/expenses/import-freeform/preview",
        json={"rawInput": RAW},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    row = body["rows"][0]

    confirm = await app_client.post(
        "/api/v1/expenses/import-freeform/confirm",
        json={
            "importId": body["importId"],
            "rawInput": RAW,
            "creates": [
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "name": row["name"],
                    "amount": row["amount"],
                    "date": row["date"],
                    "note": row["note"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "importance": row["suggestedImportance"],
                }
            ],
            "categoryUpdates": [],
        },
    )
    assert confirm.status_code == 201, confirm.text
    assert confirm.json()["created"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert any(e["name"] == "Coffee" for e in expenses)

    logs = (await app_client.get("/api/v1/import-logs")).json()
    assert logs, "expected an import log entry"
    latest = logs[0]
    assert latest["source"] == "freeform"
    assert latest["rawInput"] == RAW
    assert latest["imported"] == 1
    assert latest["files"] == []


async def test_freeform_confirm_is_idempotent(app_client, monkeypatch):
    """Confirming the same free-form import twice must not double-import.

    The confirm path re-runs the dedup against the DB at write time using
    (date, name, amount, note), so re-submitting an identical create row is a
    no-op. Editing the amount makes it a genuinely different transaction that
    is created once.
    """
    monkeypatch.setattr(
        "quid_api.routers.expenses.parse_freeform_transactions",
        _fake_parse([ParsedFreeformItem(name="Coffee", amount="3.50", date="2026-04-01", note="")]),
    )
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})

    preview = await app_client.post(
        "/api/v1/expenses/import-freeform/preview",
        json={"rawInput": "coffee 3.50 on 2026-04-01"},
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    import_id = preview.json()["importId"]

    def confirm_payload(amount: object) -> dict[str, object]:
        return {
            "importId": import_id,
            "rawInput": "coffee 3.50 on 2026-04-01",
            "creates": [
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "name": row["name"],
                    "amount": amount,
                    "date": row["date"],
                    "note": row["note"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "importance": row["suggestedImportance"],
                }
            ],
            "categoryUpdates": [],
        }

    first = await app_client.post(
        "/api/v1/expenses/import-freeform/confirm", json=confirm_payload(3.50)
    )
    assert first.status_code == 201, first.text
    assert first.json()["created"] == 1

    # Same transaction again → deduped, nothing new created.
    second = await app_client.post(
        "/api/v1/expenses/import-freeform/confirm", json=confirm_payload(3.50)
    )
    assert second.status_code == 201, second.text
    assert second.json()["created"] == 0
    assert second.json()["skippedDuplicates"] == 1

    # Edited amount → a different transaction, created once.
    edited = await app_client.post(
        "/api/v1/expenses/import-freeform/confirm", json=confirm_payload(9.99)
    )
    assert edited.status_code == 201, edited.text
    assert edited.json()["created"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    coffees = [e for e in expenses if e["name"] == "Coffee"]
    assert len(coffees) == 2
    assert sorted(e["amount"] for e in coffees) == [3.50, 9.99]


async def test_csv_import_log_reports_csv_source(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    resp = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            (
                "files",
                (
                    "a.csv",
                    b"name,category,amount,date\nPret,eating_out,-3.50,2026-04-01\n",
                    "text/csv",
                ),
            )
        ],
    )
    assert resp.status_code == 201, resp.text
    logs = (await app_client.get("/api/v1/import-logs")).json()
    assert logs[0]["source"] == "csv"
    assert logs[0]["rawInput"] is None
