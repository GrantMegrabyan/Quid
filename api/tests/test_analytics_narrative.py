"""Tests for the analytics narrative store (the analytics layer's only write path)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from quid_api.repositories.analytics_narrative import AnalyticsNarrativeRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess


async def test_get_latest_empty(session):
    repo = AnalyticsNarrativeRepository(session)
    assert await repo.get_latest() is None


async def test_upsert_and_get_latest(session):
    repo = AnalyticsNarrativeRepository(session)
    row = await repo.upsert(month="2026-04", content="April summary.", model="m1")
    assert row.month == "2026-04"
    later = await repo.upsert(month="2026-05", content="May summary.", model="m1")
    assert later.month == "2026-05"
    latest = await repo.get_latest()
    assert latest is not None
    assert latest.month == "2026-05"


async def test_upsert_same_month_replaces(session):
    repo = AnalyticsNarrativeRepository(session)
    first = await repo.upsert(month="2026-05", content="v1", model="m1")
    second = await repo.upsert(month="2026-05", content="v2", model="m2")
    assert second.id == first.id
    assert second.content == "v2"
    assert second.model == "m2"
    latest = await repo.get_latest()
    assert latest is not None
    assert latest.content == "v2"
