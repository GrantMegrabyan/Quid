from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from quid_api.db import get_session
from quid_api.main import create_app
from quid_api.settings import (
    Settings,
    _looks_like_test_database,
    get_settings,
)
from quid_api.settings import TestingConfigError as _TestingConfigError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


# --- validate_testing: DB-safety guard ------------------------------------


def test_validate_testing_noop_when_disabled():
    # Real-looking DB but testing off => must not raise.
    Settings(
        testing=False,
        database_url="sqlite+aiosqlite:///./.data/quid.db",
    ).validate_testing()


def test_validate_testing_rejects_real_db_when_enabled():
    with pytest.raises(_TestingConfigError, match="QUID_DATABASE_URL"):
        Settings(
            testing=True,
            testing_token="t",
            database_url="sqlite+aiosqlite:///./.data/quid.db",
        ).validate_testing()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite:///./.data/quid-test.db",
        "sqlite+aiosqlite:///./.data/quid-e2e.db",
        "sqlite+aiosqlite:///:memory:",
    ],
)
def test_validate_testing_allows_test_database(url: str):
    # Should not raise for throwaway-looking databases.
    Settings(testing=True, testing_token="t", database_url=url).validate_testing()


def test_validate_testing_override_allows_unsafe_db():
    Settings(
        testing=True,
        testing_token="t",
        testing_allow_unsafe_db=True,
        database_url="sqlite+aiosqlite:///./.data/quid.db",
    ).validate_testing()


def test_looks_like_test_database_helper():
    assert _looks_like_test_database("sqlite+aiosqlite:///quid-e2e.db") is True
    assert _looks_like_test_database("sqlite+aiosqlite:///quid-test.db") is True
    assert _looks_like_test_database("sqlite+aiosqlite:///:memory:") is True
    assert _looks_like_test_database("sqlite+aiosqlite:///quid.db") is False


def test_create_app_fails_fast_on_unsafe_testing_db():
    with pytest.raises(_TestingConfigError):
        create_app(
            settings=Settings(
                testing=True,
                testing_token="t",
                database_url="sqlite+aiosqlite:///./.data/quid.db",
            )
        )


# --- token enforcement on the testing router ------------------------------


@pytest_asyncio.fixture
async def testing_app_client_factory(engine: AsyncEngine, database_url: str):
    """Build a client against a testing app with a configurable token."""
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with sm() as sess:
            yield sess

    def _make(token: str | None):
        settings = Settings(
            database_url=database_url,
            testing=True,
            testing_token=token,
            openrouter_api_key=None,
        )
        app = create_app(settings=settings)
        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_settings] = lambda: settings
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    return _make


async def test_reset_rejects_missing_token(testing_app_client_factory):
    async with testing_app_client_factory("secret") as client:
        res = await client.post("/api/v1/testing/reset")
    assert res.status_code == 401


async def test_reset_rejects_wrong_token(testing_app_client_factory):
    async with testing_app_client_factory("secret") as client:
        res = await client.post(
            "/api/v1/testing/reset",
            headers={"X-Testing-Token": "nope"},
        )
    assert res.status_code == 401


async def test_reset_allows_correct_token(testing_app_client_factory):
    async with testing_app_client_factory("secret") as client:
        res = await client.post(
            "/api/v1/testing/reset",
            headers={"X-Testing-Token": "secret"},
        )
    assert res.status_code == 204


async def test_router_locked_when_token_unset(testing_app_client_factory):
    # Mounted (testing=True) but no token configured => fail closed with 403.
    async with testing_app_client_factory(None) as client:
        res = await client.post(
            "/api/v1/testing/reset",
            headers={"X-Testing-Token": "anything"},
        )
    assert res.status_code == 403


async def test_seed_state_requires_token(testing_app_client_factory):
    async with testing_app_client_factory("secret") as client:
        res = await client.post(
            "/api/v1/testing/seed-state",
            json={"categories": [], "expenses": []},
        )
    assert res.status_code == 401
