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


@app.command("backfill-amazon-short-names")
def backfill_amazon_short_names() -> None:
    """Generate and save AI short names for imported Amazon orders that don't
    have one yet. Never overwrites existing (possibly user-edited) names."""
    result = asyncio.run(_backfill_amazon_short_names_runner())
    typer.echo(
        f"Amazon short names: {result['named']} generated "
        f"({result['missing']} missing, {result['skipped']} already named)"
    )


async def _backfill_amazon_short_names_runner() -> dict[str, int]:
    from quid_api.ai_short_names import ShortNameInput, generate_short_names
    from quid_api.repositories.amazon_orders import (
        AmazonOrderRepository,
        deserialize_items,
    )

    settings = get_settings()
    engine = build_engine(settings)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            repo = AmazonOrderRepository(session)
            orders = await repo.list_all()
            missing = [order for order in orders if not order.short_name]
            skipped = len(orders) - len(missing)
            inputs = [
                ShortNameInput(
                    order_id=order.id,
                    item_titles=[
                        str(item["title"]) for item in deserialize_items(order.items_json)
                    ],
                )
                for order in missing
            ]
            generated = await generate_short_names(
                inputs,
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                chunk_size=settings.openrouter_chunk_size,
            )
            await repo.set_generated_short_names(generated)
            await session.commit()
            return {
                "missing": len(missing),
                "named": len(generated),
                "skipped": skipped,
            }
    finally:
        await engine.dispose()


@app.command("backfill-amazon-categories")
def backfill_amazon_categories() -> None:
    """AI-categorise already-imported Amazon orders that don't have a category
    yet, then push every categorised order's category onto its linked
    expenses that still carry a low-priority (import/AI) category. Idempotent:
    never overwrites an order's existing category nor a hand-set / import-rule
    expense category."""
    result = asyncio.run(_backfill_amazon_categories_runner())
    typer.echo(
        f"Amazon categories: {result['named']} orders categorised "
        f"({result['missing']} missing, {result['skipped']} already categorised); "
        f"{result['propagated']} expenses re-categorised from linked orders"
    )


async def _backfill_amazon_categories_runner() -> dict[str, int]:
    from sqlalchemy import select

    from quid_api.ai_order_categorization import categorize_amazon_orders
    from quid_api.models import Category
    from quid_api.repositories.ai_rules import AiRuleRepository
    from quid_api.repositories.amazon_orders import AmazonOrderRepository

    settings = get_settings()
    engine = build_engine(settings)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sm() as session:
            repo = AmazonOrderRepository(session)
            orders = await repo.list_all()
            missing = [order for order in orders if order.category_id is None]
            skipped = len(orders) - len(missing)
            category_rows = list(
                await session.execute(
                    select(Category.name, Category.description).order_by(Category.name)
                )
            )
            ai_rules = [
                rule.text for rule in await AiRuleRepository(session).list_all(enabled_only=True)
            ]
            derived = await categorize_amazon_orders(
                session,
                missing,
                existing_categories=[(row.name, row.description) for row in category_rows],
                ai_rules=ai_rules,
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                chunk_size=settings.openrouter_chunk_size,
            )
            named = await repo.set_generated_categories(derived)
            # Standalone pass: reconcile expenses linked to orders that already
            # carried a category (which set_generated_categories skips), e.g.
            # the existing "everything is Shopping" Amazon expenses.
            propagated = await repo.propagate_all_categories_to_links()
            await session.commit()
            return {
                "missing": len(missing),
                "named": named,
                "skipped": skipped,
                "propagated": propagated,
            }
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
