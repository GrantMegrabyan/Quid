"""Tests for the analytics narrative OpenRouter module."""

from __future__ import annotations

import httpx
import pytest

from quid_api.ai_narrative import generate_narrative
from quid_api.errors import RepositoryError

pytestmark = pytest.mark.asyncio


def _mock_client(content: str | None, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if content is None:
            return httpx.Response(status, json={})
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_missing_api_key_raises():
    with pytest.raises(RepositoryError, match="QUID_OPENROUTER_API_KEY"):
        await generate_narrative("{}", api_key=None, model="m")


async def test_happy_path_returns_text():
    client = _mock_client("Your spending rose 12% driven by Eating Out.")
    out = await generate_narrative('{"month": "2026-05"}', api_key="k", model="m", client=client)
    assert "Eating Out" in out


async def test_http_error_status_raises():
    client = _mock_client("irrelevant", status=500)
    with pytest.raises(RepositoryError, match="HTTP 500"):
        await generate_narrative("{}", api_key="k", model="m", client=client)


async def test_empty_content_raises():
    client = _mock_client(None)
    with pytest.raises(RepositoryError):
        await generate_narrative("{}", api_key="k", model="m", client=client)
