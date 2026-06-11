"""Tests for the analytics narrative OpenRouter module."""

from __future__ import annotations

import json

import httpx
import pytest

from quid_api.ai_narrative import generate_narrative
from quid_api.errors import RepositoryError

pytestmark = pytest.mark.asyncio


def _mock_client(content: str, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_missing_api_key_raises():
    with pytest.raises(RepositoryError, match="QUID_OPENROUTER_API_KEY"):
        await generate_narrative("{}", api_key=None, model="m")


async def test_happy_path_returns_text():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Your spending rose 12% driven by Eating Out."}}
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    facts = '{"month": "2026-05"}'
    out = await generate_narrative(facts, api_key="k", model="m", client=client)

    assert "Eating Out" in out
    assert len(captured) == 1
    body = json.loads(captured[0].content)
    user_content = next(m["content"] for m in body["messages"] if m["role"] == "user")
    assert facts in user_content
    assert captured[0].headers["Authorization"] == "Bearer k"


async def test_http_error_status_raises():
    client = _mock_client("irrelevant", status=500)
    with pytest.raises(RepositoryError, match="HTTP 500"):
        await generate_narrative("{}", api_key="k", model="m", client=client)


async def test_no_choices_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(RepositoryError):
        await generate_narrative("{}", api_key="k", model="m", client=client)


async def test_empty_content_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "   "}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(RepositoryError):
        await generate_narrative("{}", api_key="k", model="m", client=client)
