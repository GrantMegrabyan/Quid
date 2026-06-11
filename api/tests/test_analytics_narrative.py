"""Tests for the analytics narrative store (the analytics layer's only write path)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from quid_api.repositories.analytics_narrative import AnalyticsNarrativeRepository

if TYPE_CHECKING:
    from httpx import AsyncClient

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


# ---------------------------------------------------------------------------
# Endpoint tests (require app_client)
# ---------------------------------------------------------------------------


async def test_get_narrative_empty(app_client: AsyncClient) -> None:
    res = await app_client.get("/api/v1/analytics/narrative")
    assert res.status_code == 200
    assert res.json() == {"narrative": None}


async def test_post_narrative_without_key_fails_cleanly(app_client: AsyncClient) -> None:
    # conftest's app_client runs with openrouter_api_key=None.
    from tests.conftest import make_category, make_expense

    cat = await make_category(app_client, "Groceries")
    for month in ("2026-03", "2026-04", "2026-05"):
        await make_expense(
            app_client, name="Tesco", amount="50.00", date=f"{month}-10", category_id=cat["id"]
        )
    res = await app_client.post("/api/v1/analytics/narrative", json={"asOf": "2026-06-10"})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION"
    assert "QUID_OPENROUTER_API_KEY" in body["message"]


async def test_post_narrative_no_data_fails(app_client: AsyncClient) -> None:
    res = await app_client.post("/api/v1/analytics/narrative", json={"asOf": "2026-06-10"})
    assert res.status_code == 422
    assert "complete month" in res.json()["message"]


async def test_post_narrative_generates_and_persists(
    app_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.conftest import make_category, make_expense

    cat = await make_category(app_client, "Groceries")
    for month in ("2026-03", "2026-04", "2026-05"):
        await make_expense(
            app_client, name="Tesco", amount="50.00", date=f"{month}-10", category_id=cat["id"]
        )

    captured: dict[str, Any] = {}

    async def fake_generate(
        facts_json: str, *, api_key: str | None, model: str, client: Any = None
    ) -> str:
        captured["facts"] = facts_json
        return "Spending was steady."

    # The missing-key check lives inside ai_narrative.generate_narrative, which
    # this fake replaces — so the call succeeds despite app_client having no key.
    monkeypatch.setattr("quid_api.routers.analytics.ai_generate_narrative", fake_generate)

    res = await app_client.post("/api/v1/analytics/narrative", json={"asOf": "2026-06-10"})
    assert res.status_code == 200, res.text
    body = res.json()["narrative"]
    assert body["month"] == "2026-05"
    assert body["content"] == "Spending was steady."
    assert "2026-05" in captured["facts"]

    # Persisted: GET returns it.
    res2 = await app_client.get("/api/v1/analytics/narrative")
    assert res2.json()["narrative"]["content"] == "Spending was steady."
