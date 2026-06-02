from __future__ import annotations

from dataclasses import replace
from typing import Any

from quid_api.ai_categorization import CategorizedBulkItems

CANONICAL = (
    "name,category,amount,date,note\n"
    "Pret,eating_out,-3.50,2026-04-01,morning coffee\n"
    "Tesco,groceries,-12.34,2026-04-01,\n"
    "Uber,transport,-19.98,2026-04-02,\n"
)

WITH_EXTRA_COLUMNS = (
    "name,category,amount,date,note,merchant_id,currency,raw_balance\n"
    "Pret,eating_out,-3.50,2026-04-01,,M001,GBP,1234.00\n"
    "Tesco,groceries,-12.34,2026-04-01,,M002,GBP,1221.66\n"
)

REVOLUT_BANK_STATEMENT = (
    "Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance\n"
    "Card Payment,Current,2026-04-01 09:00:00,2026-04-01 09:00:01,Pret,-3.50,0.00,GBP,COMPLETED,100.00\n"
    "Card Payment,Current,2026-04-02 10:00:00,2026-04-02 10:00:01,Tesco,-12.34,0.00,GBP,COMPLETED,87.66\n"
    "Card Payment,Current,2026-04-03 11:00:00,,Pending Coffee,-2.00,0.00,GBP,PENDING,87.66\n"
)

CANONICAL_WITH_DUPES = (
    "name,category,amount,date,note\n"
    "M&S,groceries,-2.10,2026-04-01,\n"
    "M&S,groceries,-2.10,2026-04-01,\n"
    "Pret,eating_out,-3.50,2026-04-01,\n"
)


def _upload(name: str, body: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, body.encode("utf-8"), "text/csv"))


async def test_import_canonical_csv(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", CANONICAL)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 3
    assert body["skippedDuplicates"] == 0
    assert body["skippedInvalidRows"] == 0
    assert len(body["files"]) == 1
    assert body["files"][0]["filename"] == "monzo.csv"
    assert body["files"][0]["imported"] == 3


async def test_import_tolerates_extra_columns(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("with-extras.csv", WITH_EXTRA_COLUMNS)],
    )
    assert res.status_code == 201, res.text
    assert res.json()["imported"] == 2


async def test_import_revolut_bank_statement_format(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("revolut.csv", REVOLUT_BANK_STATEMENT)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 2
    assert body["skippedInvalidRows"] == 1
    expenses = (await app_client.get("/api/v1/expenses")).json()
    dates = sorted(e["date"] for e in expenses)
    # Uses Started Date (09:00:00 / 10:00:00), NOT Completed Date
    # (09:00:01 / 10:00:01), and preserves the time component.
    assert dates == ["2026-04-01T09:00:00", "2026-04-02T10:00:00"]


async def test_import_is_idempotent_on_same_file(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", CANONICAL)],
    )
    assert first.status_code == 201
    assert first.json()["imported"] == 3

    second = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", CANONICAL)],
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["imported"] == 0
    assert second_body["skippedDuplicates"] == 3
    assert second_body["files"][0]["imported"] == 0
    assert second_body["files"][0]["skippedDuplicates"] == 3

    all_expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(all_expenses) == 3


async def test_import_allows_intentional_duplicates_across_uploads(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    one_row = "name,category,amount,date,note\nM&S,groceries,-2.10,2026-04-01,\n"
    r1 = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("a.csv", one_row)],
    )
    assert r1.json()["imported"] == 1

    two_rows = (
        "name,category,amount,date,note\n"
        "M&S,groceries,-2.10,2026-04-01,\n"
        "M&S,groceries,-2.10,2026-04-01,\n"
    )
    r2 = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("b.csv", two_rows)],
    )
    body = r2.json()
    assert body["imported"] == 1
    assert body["skippedDuplicates"] == 1


async def test_import_inserts_two_identical_rows_from_same_file(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("dupes.csv", CANONICAL_WITH_DUPES)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 3
    assert body["skippedDuplicates"] == 0

    again = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("dupes.csv", CANONICAL_WITH_DUPES)],
    )
    again_body = again.json()
    assert again_body["imported"] == 0
    assert again_body["skippedDuplicates"] == 3


async def test_import_same_day_different_time_are_distinct(app_client):
    # Two transactions: same merchant, same amount, same calendar day, but
    # different wall-clock times. The time component must keep them distinct
    # (not collapsed as a duplicate).
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    same_day = (
        "name,category,amount,date,note\n"
        "Pret,eating_out,-3.50,2026-04-01 09:00:00,\n"
        "Pret,eating_out,-3.50,2026-04-01 17:30:00,\n"
    )
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("same-day.csv", same_day)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 2
    assert body["skippedDuplicates"] == 0

    expenses = (await app_client.get("/api/v1/expenses")).json()
    dates = sorted(e["date"] for e in expenses)
    assert dates == ["2026-04-01T09:00:00", "2026-04-01T17:30:00"]


async def test_import_with_time_is_idempotent(app_client):
    # Re-uploading a timestamped CSV is still a no-op: the canonical stored
    # string equals the incoming value exactly.
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    timed = (
        "name,category,amount,date,note\n"
        "Pret,eating_out,-3.50,2026-04-01 09:00:00,\n"
        "Tesco,groceries,-12.34,2026-04-02 10:15:42,\n"
    )
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("timed.csv", timed)],
    )
    assert first.json()["imported"] == 2
    second = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("timed.csv", timed)],
    )
    second_body = second.json()
    assert second_body["imported"] == 0
    assert second_body["skippedDuplicates"] == 2

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 2


async def test_import_multiple_files_combined(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    monzo = "name,category,amount,date,note\nPret,eating_out,-3.50,2026-04-01,\n"
    revolut = "name,category,amount,date,note\nStarbucks,eating_out,-10.00,2026-04-01,\n"
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload("monzo.csv", monzo),
            _upload("revolut.csv", revolut),
        ],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 2
    assert len(body["files"]) == 2
    by_name = {f["filename"]: f for f in body["files"]}
    assert by_name["monzo.csv"]["imported"] == 1
    assert by_name["revolut.csv"]["imported"] == 1


async def test_import_rejects_csv_missing_required_columns(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    bad = "foo,bar\n1,2\n"
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("bad.csv", bad)],
    )
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION"
    assert "bad.csv" in body["message"]


async def test_import_rejects_empty_file_list(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post("/api/v1/expenses/import-csv")
    assert res.status_code == 422


async def test_import_skips_invalid_rows_within_file(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    mixed = (
        "name,category,amount,date,note\n"
        "Pret,eating_out,-3.50,2026-04-01,\n"
        ",,,,\n"
        "Tesco,groceries,not-a-number,2026-04-01,\n"
        "Uber,transport,-19.98,2026-04-02,\n"
    )
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("mixed.csv", mixed)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 2
    assert body["skippedInvalidRows"] == 2


async def test_import_dedupes_across_uploads_with_category_drift(app_client, monkeypatch):
    drift = {"category": "travel"}

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        return CategorizedBulkItems(
            items=[replace(item, category=drift["category"]) for item in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})

    csv = "name,amount,date\nGg Platform,-4.31,2026-04-25\n"

    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("revolut.csv", csv)],
    )
    assert first.status_code == 201, first.text
    assert first.json()["imported"] == 1

    drift["category"] = "transport"
    second = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("revolut.csv", csv)],
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["imported"] == 0, body
    assert body["skippedDuplicates"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1


async def test_import_preview_shows_category_drift_without_saving(app_client, monkeypatch):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "first.csv", "name,category,amount,date\nGg Platform,transport,-4.31,2026-04-25\n"
            )
        ],
    )
    assert first.status_code == 201, first.text
    transport_id = first.json()["expenses"][0]["categoryId"]
    assert first.json()["expenses"][0]["categoryId"] == transport_id

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        return CategorizedBulkItems(
            items=[replace(item, category="groceries") for item in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[_upload("again.csv", "name,amount,date\nGg Platform,-4.31,2026-04-25\n")],
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"]["creates"] == 0
    assert body["summary"]["categoryUpdates"] == 1
    assert body["summary"]["hiddenDuplicates"] == 0
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["kind"] == "category_update"
    assert row["existingCategoryId"] == transport_id
    assert row["suggestedCategory"]["id"] == "cat-groceries"

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert expenses[0]["categoryId"] == transport_id


async def test_import_preview_confirm_updates_importance_drift(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "first.csv",
                "name,category,amount,date,importance\nRent,housing,-1200,2026-04-25,important\n",
            )
        ],
    )
    assert first.status_code == 201, first.text
    assert first.json()["expenses"][0]["importance"] == "important"

    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[
            _upload(
                "again.csv",
                "name,category,amount,date,importance\nRent,housing,-1200,2026-04-25,essential\n",
            )
        ],
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"]["creates"] == 0
    assert body["summary"]["categoryUpdates"] == 1
    assert body["summary"]["hiddenDuplicates"] == 0
    row = body["rows"][0]
    assert row["kind"] == "category_update"
    assert row["existingImportance"] == "important"
    assert row["suggestedImportance"] == "essential"

    confirm = await app_client.post(
        "/api/v1/expenses/import-csv/confirm",
        json={
            "importId": body["importId"],
            "creates": [],
            "categoryUpdates": [
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "existingExpenseId": row["existingExpenseId"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "importance": row["suggestedImportance"],
                    "accept": True,
                }
            ],
        },
    )
    assert confirm.status_code == 201, confirm.text
    assert confirm.json()["updated"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert expenses[0]["importance"] == "essential"


async def test_import_confirm_creates_and_updates_categories(app_client, monkeypatch):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "first.csv", "name,category,amount,date\nGg Platform,transport,-4.31,2026-04-25\n"
            )
        ],
    )

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        updated = []
        for item in items:
            category = "groceries" if item.name == "Gg Platform" else "coffee"
            updated.append(replace(item, category=category))
        return CategorizedBulkItems(items=updated, categorized=len(updated))

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    csv = "name,amount,date\nGg Platform,-4.31,2026-04-25\nPret,-3.50,2026-04-26\n"
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[_upload("again.csv", csv)],
    )
    body = preview.json()
    creates = []
    updates = []
    for row in body["rows"]:
        if row["kind"] == "create":
            creates.append(
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "name": row["name"],
                    "amount": row["amount"],
                    "date": row["date"],
                    "note": row["note"],
                    "categoryName": row["suggestedCategory"]["name"],
                }
            )
        elif row["kind"] == "category_update":
            updates.append(
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "existingExpenseId": row["existingExpenseId"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "accept": True,
                }
            )

    confirm = await app_client.post(
        "/api/v1/expenses/import-csv/confirm",
        json={"importId": body["importId"], "creates": creates, "categoryUpdates": updates},
    )
    assert confirm.status_code == 201, confirm.text
    result = confirm.json()
    assert result["created"] == 1
    assert result["updated"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    by_name = {expense["name"]: expense for expense in expenses}
    assert by_name["Gg Platform"]["categoryId"] == "cat-groceries"
    assert by_name["Pret"]["categoryId"] == "cat-coffee"


async def test_import_dedupes_across_uploads_with_name_case_drift(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    upper = "name,category,amount,date,note\nGG PLATFORM,travel,-4.31,2026-04-25,\n"
    mixed = "name,category,amount,date,note\nGg Platform,travel,-4.31,2026-04-25,\n"

    first = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("a.csv", upper)])
    assert first.json()["imported"] == 1

    second = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("b.csv", mixed)])
    assert second.json()["imported"] == 0
    assert second.json()["skippedDuplicates"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1


async def test_import_dedupes_across_uploads_with_internal_whitespace_drift(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    spaced = "name,category,amount,date,note\nGg   Platform,travel,-4.31,2026-04-25,car   park\n"
    normal = "name,category,amount,date,note\nGg Platform,travel,-4.31,2026-04-25,car park\n"

    first = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("a.csv", spaced)])
    assert first.status_code == 201, first.text
    assert first.json()["imported"] == 1

    second = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("b.csv", normal)])
    assert second.status_code == 201, second.text
    assert second.json()["imported"] == 0
    assert second.json()["skippedDuplicates"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1


async def test_import_dedupes_across_uploads_with_note_drift(app_client):
    """A note difference must not defeat dedup.

    Regression: the dedup key used to include the note, so re-importing the
    same transaction with a missing/different note (a later bank export, or a
    row whose note was edited after the first import) created a duplicate.
    """
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    with_note = "name,category,amount,date,note\nPret,eating_out,-3.50,2026-04-01,morning coffee\n"
    without_note = "name,category,amount,date,note\nPret,eating_out,-3.50,2026-04-01,\n"

    first = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("a.csv", with_note)]
    )
    assert first.status_code == 201, first.text
    assert first.json()["imported"] == 1

    # Same transaction, note now absent -> still the same transaction.
    second = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("b.csv", without_note)]
    )
    assert second.status_code == 201, second.text
    assert second.json()["imported"] == 0
    assert second.json()["skippedDuplicates"] == 1

    # And a third export with a different note still dedupes.
    other_note = "name,category,amount,date,note\nPret,eating_out,-3.50,2026-04-01,latte\n"
    third = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("c.csv", other_note)]
    )
    assert third.status_code == 201, third.text
    assert third.json()["imported"] == 0
    assert third.json()["skippedDuplicates"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1


async def test_import_can_ai_categorize_transactions(app_client, monkeypatch):
    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        assert existing_categories
        assert ai_rules
        assert api_key is None
        assert model == "google/gemini-2.5-flash"
        updated = [replace(item, category="coffee") for item in items]
        return CategorizedBulkItems(items=updated, categorized=len(updated))

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})

    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", "name,amount,date\nPret,-3.50,2026-04-01\n")],
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["transactionsFound"] == 1
    assert body["aiCategorized"] == 1
    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert expenses[0]["categoryId"] == "cat-coffee"


async def test_import_can_ai_exclude_transactions(app_client, monkeypatch):
    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        assert "Exclude transfers from categorisation/imports." in ai_rules
        updated = [replace(item, category="other") for item in items]
        return CategorizedBulkItems(
            items=updated, categorized=len(updated), excluded_indices=frozenset({0})
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})

    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", "name,amount,date\nBank Transfer,-3.50,2026-04-01\n")],
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 0
    assert body["skippedExcluded"] == 1
    assert (await app_client.get("/api/v1/expenses")).json() == []


async def test_confirm_reject_keeps_existing(app_client, monkeypatch):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "first.csv", "name,category,amount,date\nGg Platform,transport,-4.31,2026-04-25\n"
            )
        ],
    )
    assert first.status_code == 201, first.text
    existing_category_id = first.json()["expenses"][0]["categoryId"]

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        return CategorizedBulkItems(
            items=[replace(item, category="groceries") for item in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[_upload("again.csv", "name,amount,date\nGg Platform,-4.31,2026-04-25\n")],
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    row = preview_body["rows"][0]

    confirm = await app_client.post(
        "/api/v1/expenses/import-csv/confirm",
        json={
            "importId": preview_body["importId"],
            "creates": [],
            "categoryUpdates": [
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "existingExpenseId": row["existingExpenseId"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "accept": False,
                }
            ],
        },
    )
    assert confirm.status_code == 201, confirm.text
    body = confirm.json()
    assert body["keptExisting"] == 1
    assert body["updated"] == 0

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert expenses[0]["categoryId"] == existing_category_id


async def test_import_skips_incoming_money_as_income(app_client):
    # Incoming money (positive amount) — salary, transfers in, reimbursements —
    # must NOT become a positive "expense" in the sign-less model.
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = (
        "name,category,amount,date,note\n"
        "Tesco,groceries,-12.34,2026-04-01,\n"
        "Salary,income,4000.00,2026-04-01,monthly pay\n"
        "Reimbursement,income,12.22,2026-04-02,football\n"
    )
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", csv)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 1
    assert body["skippedIncome"] == 2

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1
    assert expenses[0]["name"] == "Tesco"


async def test_import_nets_out_refund_pair(app_client):
    # A refund credit that matches a prior charge cancels BOTH sides to zero,
    # rather than dropping the credit and keeping the charge as spend.
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = (
        "name,category,amount,date,note\n"
        "Amazon,shopping,-29.99,2026-04-01,\n"
        "Amazon,shopping,29.99,2026-04-05,refund\n"
        "Tesco,groceries,-12.34,2026-04-02,\n"
    )
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", csv)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 1
    assert body["skippedRefunds"] == 2
    # The matched charge is a refund, not income.
    assert body["skippedIncome"] == 0

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1
    assert expenses[0]["name"] == "Tesco"


async def test_import_preview_surfaces_income_as_excluded(app_client):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = (
        "name,category,amount,date,note\n"
        "Tesco,groceries,-12.34,2026-04-01,\n"
        "Salary,income,4000.00,2026-04-01,\n"
    )
    res = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[_upload("monzo.csv", csv)],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["summary"]["skippedIncome"] == 1
    assert body["summary"]["excluded"] == 1
    # Income is shown (as an excluded row), never silently dropped.
    kinds = sorted(row["kind"] for row in body["rows"])
    assert kinds == ["create", "excluded"]


async def test_confirm_skips_stale_update_when_expense_deleted(app_client, monkeypatch):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "first.csv", "name,category,amount,date\nGg Platform,transport,-4.31,2026-04-25\n"
            )
        ],
    )
    assert first.status_code == 201, first.text
    expense_id = first.json()["expenses"][0]["id"]

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        return CategorizedBulkItems(
            items=[replace(item, category="groceries") for item in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[_upload("again.csv", "name,amount,date\nGg Platform,-4.31,2026-04-25\n")],
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    row = preview_body["rows"][0]

    deleted = await app_client.delete(f"/api/v1/expenses/{expense_id}")
    assert deleted.status_code == 204, deleted.text

    confirm = await app_client.post(
        "/api/v1/expenses/import-csv/confirm",
        json={
            "importId": preview_body["importId"],
            "creates": [],
            "categoryUpdates": [
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "existingExpenseId": row["existingExpenseId"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "accept": True,
                }
            ],
        },
    )
    assert confirm.status_code == 201, confirm.text
    body = confirm.json()
    assert body["skippedStaleUpdates"] == 1
    assert body["updated"] == 0


async def test_confirm_skips_stale_update_when_hash_mismatch(app_client, monkeypatch):
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "first.csv", "name,category,amount,date\nGg Platform,transport,-4.31,2026-04-25\n"
            )
        ],
    )
    assert first.status_code == 201, first.text
    expense = first.json()["expenses"][0]

    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        return CategorizedBulkItems(
            items=[replace(item, category="groceries") for item in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        files=[_upload("again.csv", "name,amount,date\nGg Platform,-4.31,2026-04-25\n")],
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    row = preview_body["rows"][0]

    changed = await app_client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"amount": "5.00"},
    )
    assert changed.status_code == 200, changed.text

    confirm = await app_client.post(
        "/api/v1/expenses/import-csv/confirm",
        json={
            "importId": preview_body["importId"],
            "creates": [],
            "categoryUpdates": [
                {
                    "previewRowId": row["previewRowId"],
                    "dedupeKeyHash": row["dedupeKeyHash"],
                    "existingExpenseId": row["existingExpenseId"],
                    "categoryName": row["suggestedCategory"]["name"],
                    "accept": True,
                }
            ],
        },
    )
    assert confirm.status_code == 201, confirm.text
    body = confirm.json()
    assert body["skippedStaleUpdates"] == 1
    assert body["updated"] == 0
