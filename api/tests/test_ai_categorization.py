from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from quid_api.ai_categorization import categorize_transactions
from quid_api.errors import RepositoryError
from quid_api.repositories.expenses import BulkItem

if TYPE_CHECKING:
    from collections.abc import Callable


def _item(name: str, amount: str = "-1.00", date: str = "2026-04-01") -> BulkItem:
    return BulkItem(name=name, category="uncategorized", amount=Decimal(amount), date=date)


def _response(*, categories: list[dict[str, Any]]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps({"categories": categories})}}]}


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _prompt_from_request(body: dict[str, Any]) -> str:
    return cast("str", body["messages"][1]["content"])


async def test_empty_items_short_circuits_without_http():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_response(categories=[]))

    async with _make_client(handler) as client:
        result = await categorize_transactions(
            [],
            existing_categories=[("Coffee", "")],
            ai_rules=[],
            api_key="key",
            model="x",
            client=client,
        )

    assert result.items == []
    assert result.categorized == 0
    assert calls == []


async def test_missing_api_key_raises():
    async with _make_client(lambda r: httpx.Response(200, json=_response(categories=[]))) as client:
        with pytest.raises(RepositoryError):
            await categorize_transactions(
                [_item("Pret")],
                existing_categories=[],
                ai_rules=[],
                api_key=None,
                model="x",
                client=client,
            )


async def test_chunking_splits_request_and_maps_global_indices():
    items = [_item(f"Merchant{i}") for i in range(7)]
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        prompt = _prompt_from_request(body)
        transactions = json.loads(prompt.split("Transactions JSON: ", 1)[1])
        return httpx.Response(
            200,
            json=_response(
                categories=[
                    {
                        "index": tx["index"],
                        "category": f"Cat-{tx['name']}",
                        "importance": "important",
                        "exclude": False,
                        "confidence": 1.0,
                    }
                    for tx in transactions
                ]
            ),
        )

    async with _make_client(handler) as client:
        result = await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=[],
            api_key="key",
            model="x",
            chunk_size=3,
            client=client,
        )

    assert len(requests) == 3
    chunk_sizes = []
    for req in requests:
        prompt = _prompt_from_request(req)
        transactions = json.loads(prompt.split("Transactions JSON: ", 1)[1])
        chunk_sizes.append(len(transactions))
    assert chunk_sizes == [3, 3, 1]

    assert [it.category for it in result.items] == [f"Cat-Merchant{i}" for i in range(7)]
    assert result.categorized == 7


async def test_prior_decisions_carry_into_later_chunks():
    items = [_item("Pret"), _item("Tesco"), _item("Uber")]
    seen_prior_blocks: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = _prompt_from_request(body)
        prior_section = prompt.split("Decisions made earlier in this same import", 1)[1]
        prior_block = prior_section.split("Transactions JSON:", 1)[0]
        seen_prior_blocks.append(prior_block)
        transactions = json.loads(prompt.split("Transactions JSON: ", 1)[1])
        return httpx.Response(
            200,
            json=_response(
                categories=[
                    {
                        "index": tx["index"],
                        "category": f"Cat-{tx['name']}",
                        "importance": "important",
                        "exclude": False,
                        "confidence": 1.0,
                    }
                    for tx in transactions
                ]
            ),
        )

    async with _make_client(handler) as client:
        await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=[],
            api_key="key",
            model="x",
            chunk_size=1,
            client=client,
        )

    assert len(seen_prior_blocks) == 3
    assert "none" in seen_prior_blocks[0]
    assert "Pret -> Cat-Pret" in seen_prior_blocks[1]
    assert "Pret -> Cat-Pret" in seen_prior_blocks[2]
    assert "Tesco -> Cat-Tesco" in seen_prior_blocks[2]


async def test_exclude_indices_mapped_to_global_position():
    items = [_item(f"M{i}") for i in range(5)]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = _prompt_from_request(body)
        transactions = json.loads(prompt.split("Transactions JSON: ", 1)[1])
        return httpx.Response(
            200,
            json=_response(
                categories=[
                    {
                        "index": tx["index"],
                        "category": "Other",
                        "importance": "important",
                        "exclude": tx["index"] == 0,
                        "confidence": 1.0,
                    }
                    for tx in transactions
                ]
            ),
        )

    async with _make_client(handler) as client:
        result = await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=[],
            api_key="key",
            model="x",
            chunk_size=2,
            client=client,
        )

    assert result.excluded_indices == frozenset({0, 2, 4})


async def test_existing_category_snapping_normalises_case_and_spacing():
    items = [_item("Pret")]
    existing = [("Coffee Shops", "")]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_response(
                categories=[
                    {
                        "index": 0,
                        "category": "COFFEE  shops",
                        "importance": "important",
                        "exclude": False,
                        "confidence": 1.0,
                    }
                ]
            ),
        )

    async with _make_client(handler) as client:
        result = await categorize_transactions(
            items,
            existing_categories=existing,
            ai_rules=[],
            api_key="key",
            model="x",
            client=client,
        )

    assert result.items[0].category == "Coffee Shops"


async def test_http_error_status_raises_repository_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server boom")

    async with _make_client(handler) as client:
        with pytest.raises(RepositoryError):
            await categorize_transactions(
                [_item("Pret")],
                existing_categories=[],
                ai_rules=[],
                api_key="key",
                model="x",
                client=client,
            )


async def test_chunk_size_zero_clamps_to_one_chunk_per_item():
    items = [_item("A"), _item("B")]
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        prompt = _prompt_from_request(body)
        transactions = json.loads(prompt.split("Transactions JSON: ", 1)[1])
        return httpx.Response(
            200,
            json=_response(
                categories=[
                    {
                        "index": tx["index"],
                        "category": "Misc",
                        "importance": "important",
                        "exclude": False,
                        "confidence": 1.0,
                    }
                    for tx in transactions
                ]
            ),
        )

    async with _make_client(handler) as client:
        await categorize_transactions(
            items,
            existing_categories=[],
            ai_rules=[],
            api_key="key",
            model="x",
            chunk_size=0,
            client=client,
        )

    assert len(requests) == 2
