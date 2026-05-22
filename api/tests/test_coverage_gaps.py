from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from quid_api.db import build_engine, dispose_engine
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import (
    BulkItem,
    ExpenseRepository,
    _coerce_amount,
)
from quid_api.settings import Settings


def test_coerce_amount_rejects_unknown_type():
    with pytest.raises(RepositoryError) as exc:
        _coerce_amount(object())
    assert exc.value.code == RepositoryErrorCode.VALIDATION


def test_coerce_amount_rejects_bad_string():
    with pytest.raises(RepositoryError) as exc:
        _coerce_amount("not a number")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


def test_coerce_amount_int_path():
    assert _coerce_amount(5) == Decimal(5)


def test_coerce_amount_decimal_path():
    d = Decimal("12.34")
    assert _coerce_amount(d) is d


async def test_bulk_create_with_empty_items_returns_empty(session):
    repo = ExpenseRepository(session)
    result = await repo.bulk_create([])
    assert result.expenses == []
    assert result.categories_created == []


async def test_bulk_create_reuses_in_batch_category(session):
    repo = ExpenseRepository(session)
    result = await repo.bulk_create(
        [
            BulkItem(name="A", category="brand-new", amount=Decimal("1"), date="2026-04-01"),
            BulkItem(name="B", category="brand-new", amount=Decimal("2"), date="2026-04-02"),
        ]
    )
    assert len(result.expenses) == 2
    assert len(result.categories_created) == 1
    assert result.expenses[0].category_id == result.expenses[1].category_id


async def test_bulk_create_matches_existing_by_canonical_name(session):
    cat_repo = CategoryRepository(session)
    existing = await cat_repo.create(name="House Stuff")
    await session.flush()

    exp_repo = ExpenseRepository(session)
    result = await exp_repo.bulk_create(
        [BulkItem(name="X", category="house_stuff", amount=Decimal("1"), date="2026-04-01")]
    )
    assert result.expenses[0].category_id == existing.id
    assert result.categories_created == []


async def test_testing_reset_with_samples(app_client):
    res = await app_client.post("/api/v1/testing/reset?with_samples=true")
    assert res.status_code == 204
    cats = (await app_client.get("/api/v1/categories")).json()
    cat_ids = {c["id"] for c in cats}
    assert "uncategorized" in cat_ids
    assert "cat-groceries" in cat_ids
    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert len(expenses) == 17


async def test_testing_reset_without_samples(app_client):
    await app_client.post("/api/v1/categories", json={"name": "Junk"})
    res = await app_client.post("/api/v1/testing/reset")
    assert res.status_code == 204
    cats = (await app_client.get("/api/v1/categories")).json()
    assert [c["id"] for c in cats] == ["uncategorized"]
    cats0 = cats[0]
    assert cats0["name"] == "Uncategorized"


async def test_dispose_engine_resets_globals():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    eng = build_engine(settings)
    assert eng is not None
    await dispose_engine()
    asyncio.get_event_loop()


def test_import_csv_command_posts_to_api(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from quid_api.cli import app

    posted_bodies: list[dict[str, object]] = []

    class FakeResponse:
        status_code = 201
        text = ""

        def json(self) -> dict[str, object]:
            return {"created": 2, "categoriesCreated": [], "expenses": []}

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        posted_bodies.append(kwargs.get("json", {}))
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)

    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "name,category,amount,date,note\n"
        "A,groceries,-1.00,2026-04-01,\n"
        "B,bills,-2.00,2026-04-02,\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["import-csv", str(csv_path), "--api-url", "http://stub"])
    assert result.exit_code == 0, result.output
    assert len(posted_bodies) == 1
    items = posted_bodies[0]["items"]
    assert isinstance(items, list)
    assert len(items) == 2


def test_import_csv_command_propagates_failure(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from quid_api.cli import app

    class FakeResponse:
        status_code = 422
        text = '{"code":"VALIDATION","message":"bad"}'

        def json(self) -> dict[str, object]:
            return {}

    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse())

    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "name,category,amount,date,note\nA,groceries,0,2026-04-01,",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["import-csv", str(csv_path)])
    assert result.exit_code != 0
