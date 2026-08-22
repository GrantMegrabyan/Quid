"""Provenance of ``expenses.importance`` and the correction log.

The point of both is that a stored importance must say who chose it: only a
value a human actually decided is a training label, and everything else is a
guess an automatic pass may overwrite.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from quid_api.models import ImportanceCorrection
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import BulkItem, ExpenseRepository
from quid_api.repositories.import_rules import ImportRuleRepository
from tests.conftest import make_category

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import Category, ImportRule


async def _make_category(session: AsyncSession, name: str = "Groceries") -> Category:
    return await CategoryRepository(session).create(name=name)


async def _make_rule(session: AsyncSession, cat_id: str, importance: str) -> ImportRule:
    return await ImportRuleRepository(session).create(
        name="tesco",
        enabled=True,
        priority=100,
        action="categorize",
        target_category_id=cat_id,
        match_name_op="contains",
        match_name_value="tesco",
        match_amount_op=None,
        match_amount_value=None,
        match_amount_value2=None,
        match_date_from=None,
        match_date_to=None,
        set_importance=importance,
    )


async def _corrections(session: AsyncSession) -> list[ImportanceCorrection]:
    rows = await session.scalars(
        select(ImportanceCorrection).order_by(ImportanceCorrection.created_at)
    )
    return list(rows)


# --- create ---------------------------------------------------------------


async def test_create_without_importance_is_unattributed(session):
    cat = await _make_category(session)
    exp = await ExpenseRepository(session).create(
        name="x", amount="1.00", date="2026-05-25", category_id=cat.id
    )
    assert exp.importance == "important"
    assert exp.importance_source == "import"


async def test_create_with_importance_is_manual(session):
    cat = await _make_category(session)
    exp = await ExpenseRepository(session).create(
        name="x",
        amount="1.00",
        date="2026-05-25",
        category_id=cat.id,
        importance="essential",
    )
    assert exp.importance_source == "manual"


# --- update ---------------------------------------------------------------


async def test_changing_importance_marks_manual_and_logs(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="Tesco", amount="12.00", date="2026-05-25", category_id=cat.id)

    await repo.update(exp.id, importance="essential")

    assert exp.importance == "essential"
    assert exp.importance_source == "manual"
    logged = await _corrections(session)
    assert len(logged) == 1
    assert logged[0].merchant_key == "tesco"
    assert logged[0].from_importance == "important"
    assert logged[0].from_source == "import"
    assert logged[0].to_importance == "essential"
    assert logged[0].context == "edit"
    assert logged[0].expense_id == exp.id


async def test_resubmitting_the_same_importance_is_not_a_decision(session):
    """The edit modal posts the whole form; an untouched field must not relabel."""
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="Tesco", amount="12.00", date="2026-05-25", category_id=cat.id)

    await repo.update(exp.id, note="groceries", importance="important")

    assert exp.importance_source == "import"
    assert await _corrections(session) == []


# --- bulk import ----------------------------------------------------------


def _item(
    name: str,
    importance: str = "important",
    *,
    importance_manual: bool = False,
    suggested_importance: str | None = None,
) -> BulkItem:
    return BulkItem(
        name=name,
        category="Groceries",
        amount=Decimal("10.00"),
        date="2026-05-25",
        importance=importance,
        importance_manual=importance_manual,
        suggested_importance=suggested_importance,
    )


async def test_bulk_import_attributes_to_ai_when_ai_ran(session):
    result = await ExpenseRepository(session).bulk_import([_item("Tesco")], used_ai=True)
    assert result.expenses[0].importance_source == "ai"


async def test_bulk_import_attributes_to_import_without_ai(session):
    result = await ExpenseRepository(session).bulk_import([_item("Tesco")], used_ai=False)
    assert result.expenses[0].importance_source == "import"


async def test_bulk_import_attributes_a_rule_set_importance_to_the_rule(session):
    cat = await _make_category(session)
    await _make_rule(session, cat.id, "essential")
    result = await ExpenseRepository(session).bulk_import([_item("Tesco")], used_ai=True)
    assert result.expenses[0].importance == "essential"
    assert result.expenses[0].importance_source == "rule"


async def test_preview_override_outranks_the_rule_and_is_logged(session):
    """The preview had already applied the rule, so moving it away is deliberate."""
    cat = await _make_category(session)
    await _make_rule(session, cat.id, "essential")
    result = await ExpenseRepository(session).bulk_import(
        [
            _item(
                "Tesco",
                importance="discretionary",
                importance_manual=True,
                suggested_importance="essential",
            )
        ],
        used_ai=True,
    )
    row = result.expenses[0]
    assert row.importance == "discretionary"
    assert row.importance_source == "manual"

    logged = await _corrections(session)
    assert len(logged) == 1
    assert logged[0].context == "import_preview"
    assert logged[0].from_importance == "essential"
    assert logged[0].to_importance == "discretionary"


async def test_duplicate_rows_are_not_logged(session):
    """A duplicate is never inserted, so re-reviewing it teaches nothing."""
    repo = ExpenseRepository(session)
    item = _item(
        "Tesco",
        importance="essential",
        importance_manual=True,
        suggested_importance="important",
    )
    await repo.bulk_import([item], used_ai=False)
    await repo.bulk_import([item], used_ai=False)
    assert len(await _corrections(session)) == 1


# --- rules ----------------------------------------------------------------


async def test_apply_rule_to_existing_attributes_to_the_rule(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="Tesco", amount="12.00", date="2026-05-25", category_id=cat.id)
    rule = await _make_rule(session, cat.id, "essential")

    await ImportRuleRepository(session).apply_to_existing(rule.id)
    await session.refresh(exp)
    assert exp.importance == "essential"
    assert exp.importance_source == "rule"


async def test_apply_all_rules_attributes_to_the_rule(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="Tesco", amount="12.00", date="2026-05-25", category_id=cat.id)
    await _make_rule(session, cat.id, "essential")

    await ImportRuleRepository(session).apply_all_to_existing()
    await session.refresh(exp)
    assert exp.importance_source == "rule"


# --- API ------------------------------------------------------------------


async def test_expense_out_exposes_importance_source(app_client):
    cat = await make_category(app_client, "Groceries")
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Tesco",
            "amount": "10.00",
            "date": "2026-05-25",
            "categoryId": cat["id"],
            "importance": "essential",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["importanceSource"] == "manual"

    patched = await app_client.patch(
        f"/api/v1/expenses/{res.json()['id']}", json={"importance": "discretionary"}
    )
    assert patched.status_code == 200
    assert patched.json()["importanceSource"] == "manual"
