from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from alembic import command
from quid_api.db import build_engine
from quid_api.main import configure_logging
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import ExpenseRepository
from quid_api.seed import reset_and_seed, seed_samples
from quid_api.settings import get_settings

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Quid API toolkit.")


@app.callback()
def _bootstrap() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)


REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def _alembic_cfg(database_url: str | None = None) -> AlembicConfig:
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    if database_url is not None:
        cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@app.command()
def migrate(
    down: Annotated[
        int | None,
        typer.Option(
            "--down",
            help="Downgrade by N revisions instead of upgrading to head.",
            min=1,
        ),
    ] = None,
) -> None:
    cfg = _alembic_cfg()
    if down is None:
        command.upgrade(cfg, "head")
    else:
        command.downgrade(cfg, f"-{down}")


@app.command()
def seed(
    reset: Annotated[
        bool,
        typer.Option(
            "--reset/--no-reset",
            help="Delete non-uncategorized data before inserting samples.",
        ),
    ] = False,
) -> None:
    counts = asyncio.run(_seed_runner(reset=reset))
    typer.echo(f"Seeded: +{counts['categories']} categories, +{counts['expenses']} expenses")


@app.command("clear-transactions")
def clear_transactions() -> None:
    counts = asyncio.run(_clear_transactions_runner())
    typer.echo(f"Cleared: {counts['expenses']} expenses, {counts['import_logs']} import logs")


async def _seed_runner(*, reset: bool) -> dict[str, int]:
    settings = get_settings()
    engine = build_engine(settings)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            cat_repo = CategoryRepository(session)
            exp_repo = ExpenseRepository(session)
            counts = (
                await reset_and_seed(cat_repo, exp_repo)
                if reset
                else await seed_samples(cat_repo, exp_repo)
            )
            await session.commit()
            return counts
    finally:
        await engine.dispose()


async def _clear_transactions_runner() -> dict[str, int]:
    settings = get_settings()
    engine = build_engine(settings)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            exp_r = await session.execute(text("DELETE FROM expenses"))
            log_r = await session.execute(text("DELETE FROM import_logs"))
            await session.commit()
            # CursorResult.rowcount is -1 when the DB doesn't report it; treat as 0
            exp_count = max(0, exp_r.rowcount)  # type: ignore[attr-defined]
            log_count = max(0, log_r.rowcount)  # type: ignore[attr-defined]
            return {"expenses": exp_count, "import_logs": log_count}
    finally:
        await engine.dispose()


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port.")] = 8000,
    reload: Annotated[bool, typer.Option("--reload/--no-reload")] = False,
    log_level: Annotated[str, typer.Option("--log-level")] = "info",
) -> None:
    uvicorn.run(
        "quid_api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        factory=False,
    )


@app.command("import-csv")
def import_csv(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="One or more CSV files with columns: name,category,amount,date,note",
        ),
    ],
    api_url: Annotated[
        str,
        typer.Option(
            "--api-url",
            envvar="QUID_API_URL",
            help="Base URL of a running Quid API.",
        ),
    ] = "http://localhost:8000",
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            help="Max items per HTTP request (server limit is 5000).",
            min=1,
            max=5000,
        ),
    ] = 1000,
) -> None:
    total_created = 0
    total_categories: set[str] = set()
    for path in paths:
        items = _read_csv(path)
        typer.echo(f"{path.name}: {len(items)} rows")
        for chunk_start in range(0, len(items), batch_size):
            chunk = items[chunk_start : chunk_start + batch_size]
            response = httpx.post(
                f"{api_url.rstrip('/')}/api/v1/expenses/bulk",
                json={"items": chunk},
                timeout=60.0,
            )
            if response.status_code != 201:
                typer.echo(f"  FAILED ({response.status_code}): {response.text}", err=True)
                raise typer.Exit(code=1)
            body = response.json()
            total_created += body["created"]
            for cat in body["categoriesCreated"]:
                total_categories.add(cat["id"])
    typer.echo(
        f"Imported {total_created} expenses; new categories created: {len(total_categories)}"
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            rows.append(
                {
                    "name": (raw.get("name") or "").strip(),
                    "category": (raw.get("category") or "").strip(),
                    "amount": (raw.get("amount") or "").strip(),
                    "date": (raw.get("date") or "").strip(),
                    "note": (raw.get("note") or "").strip(),
                }
            )
    return rows


if __name__ == "__main__":
    app()
