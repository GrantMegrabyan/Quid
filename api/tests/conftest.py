from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def _build_alembic_config(database_url: str) -> AlembicConfig:
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "quid-test.db"


@pytest.fixture
def database_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    from sqlalchemy import event

    def _fk_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    cfg = _build_alembic_config(database_url)
    await asyncio.to_thread(command.upgrade, cfg, "head")

    eng = create_async_engine(database_url, future=True)
    event.listen(eng.sync_engine, "connect", _fk_pragma)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess
        await sess.rollback()


@pytest_asyncio.fixture
async def app_client(engine: AsyncEngine, database_url: str):
    from httpx import ASGITransport, AsyncClient

    from quid_api.db import get_session
    from quid_api.main import create_app
    from quid_api.settings import Settings

    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with sm() as sess:
            yield sess

    settings = Settings(database_url=database_url, testing=True)
    app = create_app(settings=settings)
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
