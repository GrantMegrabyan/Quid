from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from quid_api.settings import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def ensure_sqlite_dir(database_url: str) -> None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return
    raw = database_url[len(prefix) :]
    if raw == ":memory:" or raw.startswith("file:"):
        return
    path = Path(raw)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_fk(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def build_engine(settings: Settings | None = None) -> AsyncEngine:
    cfg = settings or get_settings()
    ensure_sqlite_dir(cfg.database_url)
    engine = create_async_engine(cfg.database_url, future=True)
    if cfg.database_url.startswith("sqlite"):
        event.listen(engine.sync_engine, "connect", _enable_sqlite_fk)
    return engine


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = build_engine()
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def configure_engine(engine: AsyncEngine) -> None:
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
