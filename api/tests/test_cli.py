from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from typer.testing import CliRunner

from quid_api.cli import app
from quid_api.models import Category, Expense, ImportRule
from quid_api.seed import CATEGORY_SEEDS, seed_samples
from quid_api.settings import reset_settings

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


def _run(args: list[str], env: dict[str, str]) -> object:
    runner = CliRunner()
    old_env = dict(os.environ)
    os.environ.update(env)
    reset_settings()
    try:
        return runner.invoke(app, args)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        reset_settings()


def test_migrate_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "quid.db"
    env = {"QUID_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    result = _run(["migrate"], env)
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert db.exists()


def test_seed_after_migrate_inserts_samples(tmp_path: Path) -> None:
    db = tmp_path / "quid.db"
    env = {"QUID_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    assert _run(["migrate"], env).exit_code == 0  # type: ignore[attr-defined]
    result = _run(["seed"], env)
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "Seeded:" in result.output  # type: ignore[attr-defined]


def test_seed_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "quid.db"
    env = {"QUID_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    assert _run(["migrate"], env).exit_code == 0  # type: ignore[attr-defined]
    first = _run(["seed"], env)
    second = _run(["seed"], env)
    assert first.exit_code == 0  # type: ignore[attr-defined]
    assert second.exit_code == 0  # type: ignore[attr-defined]
    assert "+0 categories, +0 expenses" in second.output  # type: ignore[attr-defined]


def test_seed_reset_replaces_data(tmp_path: Path) -> None:
    db = tmp_path / "quid.db"
    env = {"QUID_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    assert _run(["migrate"], env).exit_code == 0  # type: ignore[attr-defined]
    _run(["seed"], env)
    result = _run(["seed", "--reset"], env)
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "+5 categories" in result.output  # type: ignore[attr-defined]


def test_help_lists_all_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("migrate", "seed", "clear-transactions", "serve", "import-csv"):
        assert cmd in result.output


def test_read_csv_parses_bank_export_format(tmp_path: Path) -> None:
    from quid_api.cli import _read_csv

    csv_path = tmp_path / "bank.csv"
    csv_path.write_text(
        "name,category,amount,date,note\n"
        "Coffee,eating_out,-3.50,2026-04-01,\n"
        "Bus fare,transport,-1.75,2026-04-02,morning\n",
        encoding="utf-8",
    )
    rows = _read_csv(csv_path)
    assert rows == [
        {
            "name": "Coffee",
            "category": "eating_out",
            "amount": "-3.50",
            "date": "2026-04-01",
            "note": "",
        },
        {
            "name": "Bus fare",
            "category": "transport",
            "amount": "-1.75",
            "date": "2026-04-02",
            "note": "morning",
        },
    ]


def test_read_csv_handles_missing_trailing_newline(tmp_path: Path) -> None:
    from quid_api.cli import _read_csv

    csv_path = tmp_path / "bank.csv"
    csv_path.write_text(
        "name,category,amount,date,note\nCoffee,eating_out,-3.50,2026-04-01,",
        encoding="utf-8",
    )
    rows = _read_csv(csv_path)
    assert len(rows) == 1
    assert rows[0]["name"] == "Coffee"


async def test_clear_transactions_keeps_rules_and_seed_categories(
    app_client, session: AsyncSession, database_url: str
) -> None:
    from quid_api.cli import _clear_transactions_runner
    from quid_api.repositories.categories import CategoryRepository
    from quid_api.repositories.expenses import ExpenseRepository

    cat_repo = CategoryRepository(session)
    exp_repo = ExpenseRepository(session)
    await seed_samples(cat_repo, exp_repo)

    protected = Category(
        id=f"cat-{uuid4()}",
        name="Protected",
        color="#123456",
        icon="house",
    )
    orphan = Category(
        id=f"cat-{uuid4()}",
        name="Disposable",
        color="#654321",
        icon="coffee",
    )
    session.add_all([protected, orphan])
    await session.flush()
    session.add(
        ImportRule(
            id=f"rule-{uuid4()}",
            name="Keep protected",
            enabled=True,
            priority=1,
            action="categorize",
            target_category_id=protected.id,
            match_name_op="contains",
            match_name_value="Coffee",
            match_amount_op=None,
            match_amount_value=None,
            match_amount_value2=None,
            match_date_from=None,
            match_date_to=None,
            created_at="2026-05-23T00:00:00Z",
        )
    )
    session.add(
        Expense(
            id=f"exp-{uuid4()}",
            name="Temp expense",
            amount=Decimal("1"),
            date="2026-05-23",
            category_id=orphan.id,
            note="",
        )
    )
    await session.commit()

    old_env = dict(os.environ)
    os.environ["QUID_DATABASE_URL"] = database_url
    reset_settings()
    try:
        counts = await _clear_transactions_runner()
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        reset_settings()

    assert counts == {"expenses": 18, "categories": 1}

    expenses = (await app_client.get("/api/v1/expenses")).json()
    rules = (await app_client.get("/api/v1/import-rules")).json()
    categories = (await app_client.get("/api/v1/categories")).json()

    assert expenses == []
    assert len(rules) == 2
    assert any(row["id"] == protected.id for row in categories)
    assert any(row["id"] == seed.id for seed in CATEGORY_SEEDS for row in categories)
    assert all(row["id"] != orphan.id for row in categories)
