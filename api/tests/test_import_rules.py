from __future__ import annotations

from decimal import Decimal

import pytest

from quid_api.models import ImportRule
from quid_api.repositories.import_rules import RuleMatchItem, _clean_name, matches_rule


def _upload(name: str, body: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, body.encode("utf-8"), "text/csv"))


def _date_rule(date_from: str | None, date_to: str | None) -> ImportRule:
    return ImportRule(
        id="r",
        name="date-only",
        enabled=True,
        priority=100,
        action="exclude",
        match_date_from=date_from,
        match_date_to=date_to,
        created_at="2026-04-01",
    )


@pytest.mark.parametrize(
    ("date_from", "date_to", "expense_date", "expected"),
    [
        # Inclusive upper bound must still match a timestamped txn on the
        # boundary day (regression guard: "...T13:45:30" > "2024-01-15").
        (None, "2026-04-15", "2026-04-15T13:45:30", True),
        # Inclusive lower bound, timestamped txn on the from-day.
        ("2026-04-15", None, "2026-04-15T00:00:01", True),
        # A timestamped txn the day after the upper bound is excluded.
        (None, "2026-04-15", "2026-04-16T00:00:00", False),
        # A timestamped txn the day before the lower bound is excluded.
        ("2026-04-15", None, "2026-04-14T23:59:59", False),
        # Bare-date expense still works.
        ("2026-04-01", "2026-04-30", "2026-04-15", True),
    ],
)
def test_rule_date_bounds_match_timestamped_expense(date_from, date_to, expense_date, expected):
    rule = _date_rule(date_from, date_to)
    item = RuleMatchItem(name="anything", amount=Decimal("1.00"), date=expense_date)
    assert matches_rule(rule, item) is expected


async def test_default_transfer_rule_is_seeded(app_client):
    res = await app_client.get("/api/v1/import-rules")
    assert res.status_code == 200
    rules = res.json()
    assert rules[0]["id"] == "rule-exclude-transfers"
    assert rules[0]["action"] == "exclude"
    assert rules[0]["matchNameOp"] == "contains"
    assert rules[0]["matchNameValue"] == "transfer"


async def test_transfer_rows_are_not_modified_on_import(app_client):
    # The CSV "Type" column value should NOT be prepended to the name.
    # Names must be stored verbatim from the CSV description/name column.
    csv = (
        "Type,Completed Date,Description,Amount,State\n"
        "Transfer,2026-04-01 09:00:00,Pocket Withdrawal,-100.00,COMPLETED\n"
        "Card Payment,2026-04-01 10:00:00,Pret,-3.50,COMPLETED\n"
    )
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("bank.csv", csv)])
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["imported"] == 2
    assert body["skippedExcluded"] == 0
    expenses = (await app_client.get("/api/v1/expenses")).json()
    names = {e["name"] for e in expenses}
    assert "Pocket Withdrawal" in names
    assert "Pret" in names
    # Names must NOT have been prefixed with "Transfer · "
    assert not any("Transfer ·" in e["name"] for e in expenses)


async def test_categorize_rule_by_name_amount_and_date(app_client):
    cat = (
        await app_client.post("/api/v1/categories", json={"name": "Rent", "icon": "house"})
    ).json()
    res = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Rent over 1000",
            "priority": 5,
            "action": "categorize",
            "targetCategoryId": cat["id"],
            "matchNameOp": "contains",
            "matchNameValue": "safeland",
            "matchAmountOp": "gte",
            "matchAmountValue": 1000,
            "matchDateFrom": "2026-04-01",
            "matchDateTo": "2026-04-30",
        },
    )
    assert res.status_code == 201, res.text

    csv = (
        "name,category,amount,date,note\n"
        "Safeland Active Management Ltd,other,-3445.00,2026-04-22,\n"
        "Safeland Active Management Ltd,other,-20.00,2026-04-22,\n"
        "Safeland Active Management Ltd,other,-3445.00,2026-05-01,\n"
    )
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    imported = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("rent.csv", csv)]
    )
    assert imported.status_code == 201, imported.text
    rows = (await app_client.get("/api/v1/expenses")).json()
    rent_rows = [e for e in rows if e["categoryId"] == cat["id"]]
    assert len(rent_rows) == 1
    assert rent_rows[0]["amount"] == "3445.00"


async def test_rule_priority_first_match_wins(app_client):
    groceries = (
        await app_client.post(
            "/api/v1/categories", json={"name": "Groceries", "icon": "shopping-cart"}
        )
    ).json()
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Exclude M&S",
            "priority": 1,
            "action": "exclude",
            "matchNameOp": "contains",
            "matchNameValue": "M&S",
        },
    )
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Categorize M&S",
            "priority": 2,
            "action": "categorize",
            "targetCategoryId": groceries["id"],
            "matchNameOp": "contains",
            "matchNameValue": "M&S",
        },
    )
    csv = "name,category,amount,date,note\nM&S,other,-2.10,2026-04-01,\n"
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    res = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("ms.csv", csv)])
    assert res.status_code == 201
    assert res.json()["skippedExcluded"] == 1
    assert (await app_client.get("/api/v1/expenses")).json() == []


async def test_apply_existing_categorize_and_exclude(app_client):
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "Safeland Active Management Ltd",
                    "category": "other",
                    "amount": -3445,
                    "date": "2026-04-22",
                    "note": "",
                },
                {
                    "name": "Transfer · Pocket Withdrawal",
                    "category": "other",
                    "amount": -100,
                    "date": "2026-04-23",
                    "note": "",
                },
            ]
        },
    )
    rule = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Rent existing",
                "action": "categorize",
                "targetCategoryId": home["id"],
                "matchNameOp": "contains",
                "matchNameValue": "Safeland",
                "matchAmountOp": "gte",
                "matchAmountValue": 1000,
            },
        )
    ).json()
    applied = await app_client.post(f"/api/v1/import-rules/{rule['id']}/apply")
    assert applied.status_code == 200
    assert applied.json() == {"matched": 1, "updated": 1, "deleted": 0}

    transfer_applied = await app_client.post("/api/v1/import-rules/rule-exclude-transfers/apply")
    assert transfer_applied.status_code == 200
    assert transfer_applied.json() == {"matched": 1, "updated": 0, "deleted": 1}
    rows = (await app_client.get("/api/v1/expenses")).json()
    assert len(rows) == 1
    assert rows[0]["categoryId"] == home["id"]


async def test_apply_existing_sets_display_name(app_client):
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "MARIA ANDREEVA REF 99281",
                    "category": "other",
                    "amount": -500,
                    "date": "2026-04-22",
                    "note": "",
                }
            ]
        },
    )
    rule = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Maria Andreeva",
                "action": "categorize",
                "targetCategoryId": home["id"],
                "matchNameOp": "contains",
                "matchNameValue": "MARIA ANDREEVA",
                "setDisplayName": "Maria Andreeva",
            },
        )
    ).json()

    applied = await app_client.post(f"/api/v1/import-rules/{rule['id']}/apply")
    assert applied.status_code == 200
    assert applied.json() == {"matched": 1, "updated": 1, "deleted": 0}

    rows = (await app_client.get("/api/v1/expenses")).json()
    assert len(rows) == 1
    assert rows[0]["displayName"] == "Maria Andreeva"


async def test_apply_all_sets_display_name(app_client):
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "MARIA ANDREEVA REF 99281",
                    "category": "other",
                    "amount": -500,
                    "date": "2026-04-22",
                    "note": "",
                }
            ]
        },
    )
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Maria Andreeva",
            "action": "categorize",
            "targetCategoryId": home["id"],
            "matchNameOp": "contains",
            "matchNameValue": "MARIA ANDREEVA",
            "setDisplayName": "Maria Andreeva",
        },
    )

    applied = await app_client.post("/api/v1/import-rules/apply-all")
    assert applied.status_code == 200
    assert applied.json()["updated"] == 1

    rows = (await app_client.get("/api/v1/expenses")).json()
    assert len(rows) == 1
    assert rows[0]["displayName"] == "Maria Andreeva"


async def test_set_note_round_trips_through_create_and_list(app_client):
    created = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Coffee note",
                "action": "exclude",
                "matchNameOp": "contains",
                "matchNameValue": "coffee",
                "setNote": "Coffee run",
            },
        )
    ).json()
    assert created["setNote"] == "Coffee run"

    defaulted = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "No note",
                "action": "exclude",
                "matchNameOp": "contains",
                "matchNameValue": "tea",
            },
        )
    ).json()
    assert defaulted["setNote"] is None

    rules = (await app_client.get("/api/v1/import-rules")).json()
    by_name = {rule["name"]: rule for rule in rules}
    assert by_name["Coffee note"]["setNote"] == "Coffee run"
    assert by_name["No note"]["setNote"] is None


async def test_apply_existing_sets_note(app_client):
    groceries = (
        await app_client.post(
            "/api/v1/categories", json={"name": "Groceries", "icon": "shopping-cart"}
        )
    ).json()
    created = (
        await app_client.post(
            "/api/v1/expenses",
            json={
                "name": "STARBUCKS #123",
                "amount": 5.25,
                "date": "2026-01-15",
                "categoryId": "uncategorized",
                "note": "original note",
            },
        )
    ).json()
    rule = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Starbucks note",
                "action": "categorize",
                "targetCategoryId": groceries["id"],
                "matchNameOp": "contains",
                "matchNameValue": "starbucks",
                "setNote": "Coffee run",
            },
        )
    ).json()

    applied = await app_client.post(f"/api/v1/import-rules/{rule['id']}/apply")
    assert applied.status_code == 200
    assert applied.json() == {"matched": 1, "updated": 1, "deleted": 0}

    rows = (await app_client.get("/api/v1/expenses")).json()
    row = next(e for e in rows if e["id"] == created["id"])
    assert row["note"] == "Coffee run"


async def test_apply_all_sets_note_overrides_existing(app_client):
    groceries = (
        await app_client.post(
            "/api/v1/categories", json={"name": "Groceries", "icon": "shopping-cart"}
        )
    ).json()
    created = (
        await app_client.post(
            "/api/v1/expenses",
            json={
                "name": "STARBUCKS #123",
                "amount": 5.25,
                "date": "2026-01-15",
                "categoryId": "uncategorized",
                "note": "original note",
            },
        )
    ).json()
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Starbucks note",
            "action": "categorize",
            "targetCategoryId": groceries["id"],
            "matchNameOp": "contains",
            "matchNameValue": "starbucks",
            "setNote": "Coffee run",
        },
    )

    applied = await app_client.post("/api/v1/import-rules/apply-all")
    assert applied.status_code == 200
    assert applied.json()["updated"] == 1

    rows = (await app_client.get("/api/v1/expenses")).json()
    row = next(e for e in rows if e["id"] == created["id"])
    assert row["note"] == "Coffee run"


async def test_import_csv_applies_set_note(app_client):
    groceries = (
        await app_client.post(
            "/api/v1/categories", json={"name": "Groceries", "icon": "shopping-cart"}
        )
    ).json()
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Starbucks note",
            "action": "categorize",
            "targetCategoryId": groceries["id"],
            "matchNameOp": "contains",
            "matchNameValue": "starbucks",
            "setNote": "Coffee run",
        },
    )

    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = "name,category,amount,date,note\nSTARBUCKS #123,other,-5.25,2026-01-15,original note\n"
    imported = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("starbucks.csv", csv)]
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["imported"] == 1

    rows = (await app_client.get("/api/v1/expenses")).json()
    assert len(rows) == 1
    assert rows[0]["note"] == "Coffee run"


async def test_rule_update_and_delete(app_client):
    created = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Coffee",
                "enabled": True,
                "priority": 10,
                "action": "exclude",
                "matchNameOp": "equals",
                "matchNameValue": "Pret",
            },
        )
    ).json()
    patched = await app_client.patch(
        f"/api/v1/import-rules/{created['id']}",
        json={
            "enabled": False,
            "priority": 42,
            "matchAmountOp": "between",
            "matchAmountValue": 1,
            "matchAmountValue2": 10,
        },
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["enabled"] is False
    assert body["priority"] == 42
    assert body["matchAmountOp"] == "between"
    deleted = await app_client.delete(f"/api/v1/import-rules/{created['id']}")
    assert deleted.status_code == 204
    missing = await app_client.get(f"/api/v1/import-rules/{created['id']}")
    assert missing.status_code == 404


async def test_apply_all_rules_applies_every_enabled_rule(app_client):
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    coffee = (await app_client.post("/api/v1/categories", json={"name": "Coffee"})).json()
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "Safeland Active Management Ltd",
                    "category": "other",
                    "amount": -3445,
                    "date": "2026-04-22",
                    "note": "",
                },
                {
                    "name": "Pret",
                    "category": "other",
                    "amount": -3.50,
                    "date": "2026-04-23",
                    "note": "",
                },
                {
                    "name": "Transfer · Pocket Withdrawal",
                    "category": "other",
                    "amount": -100,
                    "date": "2026-04-23",
                    "note": "",
                },
            ]
        },
    )
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Rent",
            "priority": 5,
            "action": "categorize",
            "targetCategoryId": home["id"],
            "matchNameOp": "contains",
            "matchNameValue": "Safeland",
        },
    )
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Coffee",
            "priority": 10,
            "action": "categorize",
            "targetCategoryId": coffee["id"],
            "matchNameOp": "equals",
            "matchNameValue": "Pret",
        },
    )

    applied = await app_client.post("/api/v1/import-rules/apply-all")
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body == {"matched": 3, "updated": 2, "deleted": 1}

    rows = (await app_client.get("/api/v1/expenses")).json()
    by_name = {e["name"]: e for e in rows}
    assert "Transfer · Pocket Withdrawal" not in by_name
    assert by_name["Safeland Active Management Ltd"]["categoryId"] == home["id"]
    assert by_name["Pret"]["categoryId"] == coffee["id"]

    rerun = await app_client.post("/api/v1/import-rules/apply-all")
    assert rerun.status_code == 200
    assert rerun.json() == {"matched": 2, "updated": 0, "deleted": 0}


async def test_apply_all_rules_with_no_rules_is_noop(app_client):
    await app_client.delete("/api/v1/import-rules/rule-exclude-transfers")
    res = await app_client.post("/api/v1/import-rules/apply-all")
    assert res.status_code == 200
    assert res.json() == {"matched": 0, "updated": 0, "deleted": 0}


async def test_day_of_month_rule_categorizes_monthly_payments(app_client):
    bills = (await app_client.post("/api/v1/categories", json={"name": "Bills"})).json()
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "Spotify",
                    "category": "other",
                    "amount": -10,
                    "date": "2026-04-01",
                    "note": "",
                },
                {
                    "name": "Spotify",
                    "category": "other",
                    "amount": -10,
                    "date": "2026-05-01",
                    "note": "",
                },
                {
                    "name": "Spotify",
                    "category": "other",
                    "amount": -10,
                    "date": "2026-05-15",
                    "note": "",
                },
            ]
        },
    )
    rule = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Monthly Spotify",
                "action": "categorize",
                "targetCategoryId": bills["id"],
                "matchDayOfMonth": 1,
            },
        )
    ).json()
    assert rule["matchDayOfMonth"] == 1

    applied = await app_client.post(f"/api/v1/import-rules/{rule['id']}/apply")
    assert applied.status_code == 200
    assert applied.json() == {"matched": 2, "updated": 2, "deleted": 0}

    rows = (await app_client.get("/api/v1/expenses")).json()
    in_bills = [e for e in rows if e["categoryId"] == bills["id"]]
    assert {e["date"] for e in in_bills} == {"2026-04-01", "2026-05-01"}


async def test_day_of_month_validation_rejects_out_of_range(app_client):
    bad = await app_client.post(
        "/api/v1/import-rules",
        json={"name": "Bad", "action": "exclude", "matchDayOfMonth": 0},
    )
    assert bad.status_code == 422
    too_big = await app_client.post(
        "/api/v1/import-rules",
        json={"name": "Bad", "action": "exclude", "matchDayOfMonth": 32},
    )
    assert too_big.status_code == 422


async def test_disabled_rule_apply_is_noop(app_client):
    created = (
        await app_client.post(
            "/api/v1/import-rules",
            json={
                "name": "Disabled",
                "enabled": False,
                "action": "exclude",
                "matchNameOp": "contains",
                "matchNameValue": "Pret",
            },
        )
    ).json()
    res = await app_client.post(f"/api/v1/import-rules/{created['id']}/apply")
    assert res.status_code == 200
    assert res.json() == {"matched": 0, "updated": 0, "deleted": 0}


def _rule(**overrides: object) -> ImportRule:
    values: dict[str, object] = {
        "id": "rule-test",
        "name": "Test",
        "enabled": True,
        "priority": 1,
        "action": "exclude",
        "target_category_id": None,
        "match_name_op": None,
        "match_name_value": None,
        "match_amount_op": None,
        "match_amount_value": None,
        "match_amount_value2": None,
        "match_date_from": None,
        "match_date_to": None,
        "match_day_of_month": None,
        "created_at": "2026-05-23T00:00:00Z",
    }
    values.update(overrides)
    return ImportRule(**values)


def test_match_helpers_cover_name_amount_and_date_ops():
    item = RuleMatchItem(name="Marks & Spencer Food", amount=Decimal("51.40"), date="2026-04-30")
    assert matches_rule(
        _rule(match_name_op="equals", match_name_value="marks & spencer food"), item
    )
    assert matches_rule(_rule(match_name_op="starts_with", match_name_value="marks"), item)
    assert matches_rule(_rule(match_name_op="ends_with", match_name_value="food"), item)
    assert not matches_rule(_rule(match_name_op="equals", match_name_value="Marks"), item)
    assert matches_rule(_rule(match_amount_op="lte", match_amount_value=Decimal("60")), item)
    assert matches_rule(_rule(match_amount_op="eq", match_amount_value=Decimal("51.40")), item)
    assert matches_rule(
        _rule(
            match_amount_op="between",
            match_amount_value=Decimal("100"),
            match_amount_value2=Decimal("50"),
        ),
        item,
    )
    assert not matches_rule(_rule(match_date_from="2026-05-01"), item)
    assert not matches_rule(_rule(match_date_to="2026-04-01"), item)
    assert matches_rule(_rule(match_day_of_month=30), item)
    assert not matches_rule(_rule(match_day_of_month=15), item)
    assert not matches_rule(
        _rule(enabled=False, match_name_op="contains", match_name_value="marks"), item
    )
    assert not matches_rule(_rule(match_name_op="invalid", match_name_value="marks"), item)
    assert not matches_rule(_rule(match_amount_op="invalid", match_amount_value=Decimal("1")), item)
    assert not matches_rule(
        _rule(match_day_of_month=1), RuleMatchItem(name="x", amount=Decimal(1), date="not-a-date")
    )


def test_clean_name_rejects_blank():
    with pytest.raises(Exception, match="blank"):
        _clean_name("  ")


async def test_rule_validation_errors(app_client):
    blank_name = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": " ",
            "action": "exclude",
            "matchNameOp": "contains",
            "matchNameValue": "x",
        },
    )
    assert blank_name.status_code == 422
    bad_action = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Bad",
            "action": "exclude",
            "targetCategoryId": "uncategorized",
            "matchNameOp": "contains",
            "matchNameValue": "x",
        },
    )
    assert bad_action.status_code == 422
    missing_target = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Bad",
            "action": "categorize",
            "matchNameOp": "contains",
            "matchNameValue": "x",
        },
    )
    assert missing_target.status_code == 422
    missing_condition = await app_client.post(
        "/api/v1/import-rules",
        json={"name": "Bad", "action": "exclude"},
    )
    assert missing_condition.status_code == 422
    bad_between = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Bad",
            "action": "exclude",
            "matchAmountOp": "between",
            "matchAmountValue": 1,
        },
    )
    assert bad_between.status_code == 422
    missing_category = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Bad",
            "action": "categorize",
            "targetCategoryId": "cat-missing",
            "matchNameOp": "contains",
            "matchNameValue": "x",
        },
    )
    assert missing_category.status_code == 422


async def _seed_preview_expenses(app_client) -> None:
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "Safeland Active Management Ltd",
                    "category": "other",
                    "amount": -3445,
                    "date": "2026-04-22",
                    "note": "",
                },
                {
                    "name": "Safeland Active Management Ltd",
                    "category": "other",
                    "amount": -20,
                    "date": "2026-04-22",
                    "note": "",
                },
                {
                    "name": "Pret",
                    "category": "other",
                    "amount": -3.5,
                    "date": "2026-04-23",
                    "note": "",
                },
            ]
        },
    )


async def test_preview_returns_matching_expenses_without_mutating(app_client):
    await _seed_preview_expenses(app_client)
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={
            "matchNameOp": "contains",
            "matchNameValue": "safeland",
            "matchAmountOp": "gte",
            "matchAmountValue": 1000,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matched"] == 1
    assert len(body["expenses"]) == 1
    assert body["expenses"][0]["name"] == "Safeland Active Management Ltd"
    assert body["expenses"][0]["amount"] == "3445.00"

    # Dry-run must not delete or modify anything.
    rows = (await app_client.get("/api/v1/expenses")).json()
    assert len(rows) == 3


async def test_preview_for_unsaved_draft_does_not_require_category(app_client):
    await _seed_preview_expenses(app_client)
    # No action/targetCategoryId supplied — preview only evaluates conditions.
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={"matchNameOp": "contains", "matchNameValue": "pret"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matched"] == 1
    assert body["expenses"][0]["name"] == "Pret"


async def test_preview_sorts_matches_by_date_desc(app_client):
    await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {
                    "name": "Pret",
                    "category": "other",
                    "amount": -1,
                    "date": "2026-04-01",
                    "note": "",
                },
                {
                    "name": "Pret",
                    "category": "other",
                    "amount": -2,
                    "date": "2026-04-23",
                    "note": "",
                },
                {
                    "name": "Pret",
                    "category": "other",
                    "amount": -3,
                    "date": "2026-04-10",
                    "note": "",
                },
            ]
        },
    )
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={"matchNameOp": "equals", "matchNameValue": "pret"},
    )
    assert res.status_code == 200, res.text
    dates = [e["date"] for e in res.json()["expenses"]]
    assert dates == ["2026-04-23", "2026-04-10", "2026-04-01"]


async def test_preview_no_matches(app_client):
    await _seed_preview_expenses(app_client)
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={"matchNameOp": "equals", "matchNameValue": "nothing-here"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matched"] == 0
    assert body["expenses"] == []


async def test_preview_ignores_enabled_flag_and_evaluates_conditions(app_client):
    # A draft is never "enabled"; preview should still evaluate its conditions.
    await _seed_preview_expenses(app_client)
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={"matchAmountOp": "lte", "matchAmountValue": 25},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matched"] == 2  # the -20 and -3.50 rows


async def test_preview_requires_at_least_one_condition(app_client):
    res = await app_client.post("/api/v1/import-rules/preview", json={})
    assert res.status_code == 422


async def test_preview_rejects_between_without_second_value(app_client):
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={"matchAmountOp": "between", "matchAmountValue": 10},
    )
    assert res.status_code == 422


async def test_import_csv_applies_set_display_name(app_client):
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Maria display name",
            "action": "categorize",
            "targetCategoryId": home["id"],
            "matchNameOp": "contains",
            "matchNameValue": "maria",
            "setDisplayName": "Maria Andreeva",
        },
    )

    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = "name,category,amount,date,note\nMARIA ANDREEVA REF 99281,other,-500,2026-04-22,\n"
    imported = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("maria.csv", csv)]
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["imported"] == 1

    rows = (await app_client.get("/api/v1/expenses")).json()
    assert len(rows) == 1
    assert rows[0]["displayName"] == "Maria Andreeva"
    assert rows[0]["categoryId"] == home["id"]


async def test_import_csv_preview_reflects_rule_category_name_and_note(app_client):
    """Preview must show the FINAL category / display name / note a matching
    ``categorize`` rule will apply on confirm — not the raw merchant string —
    otherwise a user "fixes" what the rule already fixes."""
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Maria display name",
            "action": "categorize",
            "targetCategoryId": home["id"],
            "matchNameOp": "contains",
            "matchNameValue": "maria",
            "setDisplayName": "Maria Andreeva",
            "setNote": "Cleaner",
        },
    )

    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = (
        "name,category,amount,date,note\nMARIA ANDREEVA REF 99281,other,-500,2026-04-22,from csv\n"
    )
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview", files=[_upload("maria.csv", csv)]
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    # Raw merchant preserved (drives dedupe + confirm payload), display name and
    # note reflect the rule, and the suggested category is the rule's target.
    assert row["name"] == "MARIA ANDREEVA REF 99281"
    assert row["displayName"] == "Maria Andreeva"
    assert row["note"] == "Cleaner"
    assert row["suggestedCategory"]["name"] == "Home"
    assert row["suggestedCategory"]["id"] == home["id"]
    # Category provenance is flagged so the preview can show a "Rule" badge.
    assert row["categoryFromRule"] is True
    # The AI/CSV guess the rule overrode is surfaced (CSV "other" ⇒ the seeded
    # "Uncategorized" category), so the user sees what the rule replaced.
    assert row["overriddenCategoryName"] == "Uncategorized"


async def test_import_csv_preview_no_override_hint_when_rule_matches_ai(app_client):
    """``overriddenCategoryName`` is null when the rule picks the SAME category
    the AI/CSV already would have — no point showing "AI suggested: X → X"."""
    home = (await app_client.post("/api/v1/categories", json={"name": "Home"})).json()
    await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Maria to Home",
            "action": "categorize",
            "targetCategoryId": home["id"],
            "matchNameOp": "contains",
            "matchNameValue": "maria",
        },
    )

    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    # CSV category already resolves to "Home", so the rule changes nothing.
    csv = "name,category,amount,date\nMARIA ANDREEVA,Home,-500,2026-04-22\n"
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview", files=[_upload("maria.csv", csv)]
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    assert row["categoryFromRule"] is True
    assert row["suggestedCategory"]["name"] == "Home"
    assert row["overriddenCategoryName"] is None


async def test_import_csv_preview_display_name_none_without_rule(app_client):
    """No matching rule ⇒ ``displayName`` is null and the parsed note is kept."""
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = "name,category,amount,date,note\nTesco,Groceries,-12.50,2026-04-22,weekly shop\n"
    preview = await app_client.post(
        "/api/v1/expenses/import-csv/preview", files=[_upload("tesco.csv", csv)]
    )
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    assert row["displayName"] is None
    assert row["name"] == "Tesco"
    assert row["note"] == "weekly shop"
    # No rule matched ⇒ category is NOT flagged as rule-driven, no override hint.
    assert row["categoryFromRule"] is False
    assert row["overriddenCategoryName"] is None
