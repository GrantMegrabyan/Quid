from __future__ import annotations

from decimal import Decimal

import pytest

from quid_api.models import ImportRule
from quid_api.repositories.import_rules import RuleMatchItem, _clean_name, matches_rule


def _upload(name: str, body: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, body.encode("utf-8"), "text/csv"))


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
    imported = await app_client.post(
        "/api/v1/expenses/import-csv", files=[_upload("rent.csv", csv)]
    )
    assert imported.status_code == 201, imported.text
    rows = (await app_client.get("/api/v1/expenses")).json()
    rent_rows = [e for e in rows if e["categoryId"] == cat["id"]]
    assert len(rent_rows) == 1
    assert rent_rows[0]["amount"] == 3445.0


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
    assert not matches_rule(
        _rule(enabled=False, match_name_op="contains", match_name_value="marks"), item
    )
    assert not matches_rule(_rule(match_name_op="invalid", match_name_value="marks"), item)
    assert not matches_rule(_rule(match_amount_op="invalid", match_amount_value=Decimal("1")), item)


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
