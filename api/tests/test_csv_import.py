from __future__ import annotations

from dataclasses import replace
from typing import Any

from quid_api.ai_categorization import CategorizedBulkItems

CANONICAL = (
    "name,category,amount,date,note\n"
    "Pret,eating_out,-3.50,2026-04-01,morning coffee\n"
    "Tesco,groceries,-12.34,2026-04-01,\n"
    "Uber,transport,19.98,2026-04-02,\n"
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
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("with-extras.csv", WITH_EXTRA_COLUMNS)],
    )
    assert res.status_code == 201, res.text
    assert res.json()["imported"] == 2


async def test_import_revolut_bank_statement_format(app_client):
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
    assert dates == ["2026-04-01", "2026-04-02"]


async def test_import_is_idempotent_on_same_file(app_client):
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


async def test_import_multiple_files_combined(app_client):
    monzo = "name,category,amount,date,note\nPret,eating_out,-3.50,2026-04-01,\n"
    revolut = "name,category,amount,date,note\nStarbucks,eating_out,10.00,2026-04-01,\n"
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
    res = await app_client.post("/api/v1/expenses/import-csv")
    assert res.status_code == 422


async def test_import_skips_invalid_rows_within_file(app_client):
    mixed = (
        "name,category,amount,date,note\n"
        "Pret,eating_out,-3.50,2026-04-01,\n"
        ",,,,\n"
        "Tesco,groceries,not-a-number,2026-04-01,\n"
        "Uber,transport,19.98,2026-04-02,\n"
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

    csv = "name,amount,date\nGg Platform,-4.31,2026-04-25\n"

    first = await app_client.post(
        "/api/v1/expenses/import-csv",
        data={"ai_categorize": "true"},
        files=[_upload("revolut.csv", csv)],
    )
    assert first.status_code == 201, first.text
    assert first.json()["imported"] == 1

    drift["category"] = "transport"
    second = await app_client.post(
        "/api/v1/expenses/import-csv",
        data={"ai_categorize": "true"},
        files=[_upload("revolut.csv", csv)],
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["imported"] == 0, body
    assert body["skippedDuplicates"] == 1

    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 1


async def test_import_preview_shows_category_drift_without_saving(app_client, monkeypatch):
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
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        data={"ai_categorize": "true"},
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


async def test_import_confirm_creates_and_updates_categories(app_client, monkeypatch):
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
    csv = "name,amount,date\nGg Platform,-4.31,2026-04-25\nPret,-3.50,2026-04-26\n"
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview",
        data={"ai_categorize": "true"},
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


async def test_import_can_ai_categorize_transactions(app_client, monkeypatch):
    async def fake_categorize(items, *, existing_categories, ai_rules, api_key, model, **_: Any):
        assert existing_categories
        assert ai_rules
        assert api_key is None
        assert model == "openai/gpt-5.4-mini"
        updated = [replace(item, category="coffee") for item in items]
        return CategorizedBulkItems(items=updated, categorized=len(updated))

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake_categorize)

    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        data={"ai_categorize": "true"},
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

    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        data={"ai_categorize": "true"},
        files=[_upload("monzo.csv", "name,amount,date\nBank Transfer,-3.50,2026-04-01\n")],
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 0
    assert body["skippedExcluded"] == 1
    assert (await app_client.get("/api/v1/expenses")).json() == []
