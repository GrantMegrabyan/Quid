"""Shared OpenRouter completion handling: fence tolerance and resampling."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import BaseModel

from quid_api.ai_freeform import parse_freeform_transactions
from quid_api.ai_openrouter import (
    UnparseableCompletion,
    extract_json_object,
    parse_completion,
)
from quid_api.ai_short_names import ShortNameInput, generate_short_names
from quid_api.errors import RepositoryError

if TYPE_CHECKING:
    from collections.abc import Callable


class _Sample(BaseModel):
    value: str


def _completion(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _parse(payload: object) -> _Sample:
    return parse_completion(payload, _Sample, format_error="bad shape", log_prefix="ai.test")


def test_extract_json_object_strips_fence_and_prose():
    fenced = 'Here you go:\n```json\n{"value": "x"}\n```\nHope that helps!'
    assert json.loads(extract_json_object(fenced)) == {"value": "x"}


def test_extract_json_object_leaves_content_without_braces_alone():
    assert extract_json_object("  no json here  ") == "no json here"


def test_parse_completion_accepts_fenced_json():
    assert _parse(_completion('```json\n{"value": "x"}\n```')).value == "x"


@pytest.mark.parametrize(
    "payload",
    [
        "not a dict",
        {},
        {"choices": []},
        {"choices": ["nope"]},
        {"choices": [{"message": "nope"}]},
        {"choices": [{"message": {"content": "   "}}]},
        {"choices": [{"message": {"content": "not json"}}]},
        {"choices": [{"message": {"content": '{"wrong": "field"}'}}]},
    ],
)
def test_parse_completion_raises_unparseable_for_every_deviation(payload: object):
    with pytest.raises(UnparseableCompletion):
        _parse(payload)


async def test_freeform_retries_a_garbled_completion():
    good = json.dumps(
        {"transactions": [{"name": "Coffee", "amount": "3.50", "date": "2026-04-01", "note": ""}]}
    )
    contents = ["Sure — here are your transactions!", good]
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=_completion(contents.pop(0)))

    async with _make_client(handler) as client:
        items = await parse_freeform_transactions(
            "coffee 3.50",
            api_key="key",
            model="x",
            client=client,
        )

    assert len(calls) == 2
    assert [item.name for item in items] == ["Coffee"]


async def test_freeform_raises_after_retry_exhausted():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=_completion("still not json"))

    async with _make_client(handler) as client:
        with pytest.raises(RepositoryError, match="unexpected format"):
            await parse_freeform_transactions(
                "coffee 3.50",
                api_key="key",
                model="x",
                client=client,
            )

    assert len(calls) == 2


async def test_short_names_retries_a_garbled_completion():
    good = json.dumps({"names": [{"index": 0, "short_name": "USB-C cables"}]})
    contents = ["```\nnot really json\n```", good]
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=_completion(contents.pop(0)))

    async with _make_client(handler) as client:
        result = await generate_short_names(
            [ShortNameInput(order_id="o1", item_titles=["Anker USB-C cable 2m"])],
            api_key="key",
            model="x",
            client=client,
        )

    assert len(calls) == 2
    assert result == {"o1": "USB-C cables"}


async def test_short_names_falls_back_after_retry_exhausted():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=_completion("not json"))

    async with _make_client(handler) as client:
        result = await generate_short_names(
            [ShortNameInput(order_id="o1", item_titles=["Anker USB-C cable 2m"])],
            api_key="key",
            model="x",
            client=client,
        )

    # Two attempts, then the crude title-derived label rather than a failed import.
    assert len(calls) == 2
    assert result == {"o1": "Anker USB-C cable 2m"}
