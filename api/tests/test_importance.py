from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from quid_api.ai_categorization import categorize_transactions
from quid_api.csv_import import CsvFile, parse_csv
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import (
    DEFAULT_IMPORTANCE,
    VALID_IMPORTANCE,
    BulkItem,
    ExpenseRepository,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import Category


async def _make_category(session: AsyncSession, name: str = "Groceries") -> Category:
    return await CategoryRepository(session).create(name=name)


async def test_create_defaults_importance_to_important(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="x", amount="1.00", date="2026-05-25", category_id=cat.id)
    assert exp.importance == DEFAULT_IMPORTANCE == "important"


async def test_create_accepts_each_valid_importance(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    for value in sorted(VALID_IMPORTANCE):
        exp = await repo.create(
            name=value,
            amount="1.00",
            date="2026-05-25",
            category_id=cat.id,
            importance=value,
        )
        assert exp.importance == value


async def test_create_rejects_invalid_importance(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(
            name="x",
            amount="1.00",
            date="2026-05-25",
            category_id=cat.id,
            importance="critical",
        )
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_update_changes_importance(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(
        name="x",
        amount="1.00",
        date="2026-05-25",
        category_id=cat.id,
        importance="discretionary",
    )
    updated = await repo.update(exp.id, importance="essential")
    assert updated.importance == "essential"


async def test_bulk_create_respects_per_item_importance(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    items = [
        BulkItem(
            name="rent",
            category=cat.name,
            amount=Decimal("1200.00"),
            date="2026-05-01",
            importance="essential",
        ),
        BulkItem(
            name="wine",
            category=cat.name,
            amount=Decimal("45.00"),
            date="2026-05-02",
            importance="discretionary",
        ),
        BulkItem(
            name="other",
            category=cat.name,
            amount=Decimal("10.00"),
            date="2026-05-03",
        ),
    ]
    result = await repo.bulk_create(items)
    by_name = {exp.name: exp for exp in result.expenses}
    assert by_name["rent"].importance == "essential"
    assert by_name["wine"].importance == "discretionary"
    assert by_name["other"].importance == DEFAULT_IMPORTANCE


async def test_bulk_import_persists_importance(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    items = [
        BulkItem(
            name="rent",
            category=cat.name,
            amount=Decimal("1200.00"),
            date="2026-05-01",
            importance="essential",
        ),
    ]
    result = await repo.bulk_import(items)
    assert len(result.expenses) == 1
    assert result.expenses[0].importance == "essential"


async def test_csv_import_reads_importance_column():
    csv_text = b"name,amount,date,importance\nrent,1200,2026-05-01,essential\ncoffee,5,2026-05-02,discretionary\nfood,40,2026-05-03,\n"
    parsed = parse_csv(CsvFile(filename="t.csv", content=csv_text))
    assert len(parsed.items) == 3
    by_name = {item.name: item for item in parsed.items}
    assert by_name["rent"].importance == "essential"
    assert by_name["coffee"].importance == "discretionary"
    assert by_name["food"].importance == DEFAULT_IMPORTANCE


async def test_csv_import_unknown_importance_falls_back_to_default():
    csv_text = b"name,amount,date,importance\nthing,1,2026-05-01,critical\n"
    parsed = parse_csv(CsvFile(filename="t.csv", content=csv_text))
    assert parsed.items[0].importance == DEFAULT_IMPORTANCE


async def test_csv_import_without_importance_column_defaults_all_rows():
    csv_text = b"name,amount,date\nthing,1,2026-05-01\n"
    parsed = parse_csv(CsvFile(filename="t.csv", content=csv_text))
    assert parsed.items[0].importance == DEFAULT_IMPORTANCE


def _mock_response(*, categories: list[dict[str, Any]]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps({"categories": categories})}}]}


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_ai_assigns_per_row_importance_to_items():
    items = [
        BulkItem(name="rent", category="x", amount=Decimal("1"), date="2026-05-01"),
        BulkItem(name="netflix", category="x", amount=Decimal("1"), date="2026-05-02"),
        BulkItem(name="gucci", category="x", amount=Decimal("1"), date="2026-05-03"),
    ]
    mapping = {"rent": "essential", "netflix": "important", "gucci": "discretionary"}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = cast("str", body["messages"][1]["content"])
        transactions = json.loads(prompt.split("Transactions JSON: ", 1)[1])
        return httpx.Response(
            200,
            json=_mock_response(
                categories=[
                    {
                        "index": tx["index"],
                        "category": "Misc",
                        "importance": mapping[tx["name"]],
                        "exclude": False,
                        "confidence": 1.0,
                    }
                    for tx in transactions
                ]
            ),
        )

    async with _mock_client(handler) as client:
        result = await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=[],
            api_key="key",
            model="x",
            client=client,
        )
    by_name = {item.name: item for item in result.items}
    assert by_name["rent"].importance == "essential"
    assert by_name["netflix"].importance == "important"
    assert by_name["gucci"].importance == "discretionary"


async def test_ai_invalid_importance_falls_back_to_default():
    items = [BulkItem(name="rent", category="x", amount=Decimal("1"), date="2026-05-01")]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_mock_response(
                categories=[
                    {
                        "index": 0,
                        "category": "Misc",
                        "importance": "very-essential",
                        "exclude": False,
                        "confidence": 1.0,
                    }
                ]
            ),
        )

    async with _mock_client(handler) as client:
        result = await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=[],
            api_key="key",
            model="x",
            client=client,
        )
    assert result.items[0].importance == DEFAULT_IMPORTANCE


async def test_ai_prompt_includes_importance_guidance():
    items = [BulkItem(name="rent", category="x", amount=Decimal("1"), date="2026-05-01")]
    captured_prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_prompts.append(cast("str", body["messages"][1]["content"]))
        return httpx.Response(
            200,
            json=_mock_response(
                categories=[
                    {
                        "index": 0,
                        "category": "Misc",
                        "importance": "essential",
                        "exclude": False,
                        "confidence": 1.0,
                    }
                ]
            ),
        )

    async with _mock_client(handler) as client:
        await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=["treat Netflix as important"],
            api_key="key",
            model="x",
            client=client,
        )
    prompt = captured_prompts[0]
    assert "essential" in prompt
    assert "discretionary" in prompt
    assert "treat Netflix as important" in prompt


async def test_create_expense_via_api_with_importance(app_client, session):
    cat = await _make_category(session)
    await session.commit()
    response = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "rent",
            "amount": 1200,
            "date": "2026-05-01",
            "categoryId": cat.id,
            "importance": "essential",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["importance"] == "essential"


async def test_patch_expense_importance_via_api(app_client, session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(
        name="x",
        amount="1.00",
        date="2026-05-01",
        category_id=cat.id,
        importance="important",
    )
    await session.commit()
    response = await app_client.patch(
        f"/api/v1/expenses/{exp.id}",
        json={"importance": "discretionary"},
    )
    assert response.status_code == 200
    assert response.json()["importance"] == "discretionary"


async def test_patch_expense_rejects_unknown_importance(app_client, session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="x", amount="1.00", date="2026-05-01", category_id=cat.id)
    await session.commit()
    response = await app_client.patch(
        f"/api/v1/expenses/{exp.id}",
        json={"importance": "critical"},
    )
    assert response.status_code == 422
