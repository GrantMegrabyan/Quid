from __future__ import annotations

import os
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from quid_api.cli import app
from quid_api.settings import reset_settings

if TYPE_CHECKING:
    from pathlib import Path


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
    for cmd in ("migrate", "seed", "serve", "import-csv"):
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
        {"name": "Coffee", "category": "eating_out", "amount": "-3.50", "date": "2026-04-01", "note": ""},
        {"name": "Bus fare", "category": "transport", "amount": "-1.75", "date": "2026-04-02", "note": "morning"},
    ]


def test_read_csv_handles_missing_trailing_newline(tmp_path: Path) -> None:
    from quid_api.cli import _read_csv

    csv_path = tmp_path / "bank.csv"
    csv_path.write_text(
        "name,category,amount,date,note\n"
        "Coffee,eating_out,-3.50,2026-04-01,",
        encoding="utf-8",
    )
    rows = _read_csv(csv_path)
    assert len(rows) == 1
    assert rows[0]["name"] == "Coffee"
