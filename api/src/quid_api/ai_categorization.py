from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from quid_api.errors import RepositoryError, RepositoryErrorCode

if TYPE_CHECKING:
    from decimal import Decimal

    from quid_api.repositories.expenses import BulkItem

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class CategorizedBulkItems:
    items: list[BulkItem]
    categorized: int


class _TransactionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    index: int
    name: str
    amount: str
    date: str
    note: str
    current_category: str


class _CategorySuggestion(BaseModel):
    index: int = Field(description="The input transaction index.")
    category: str = Field(description="Short spending category name.")
    confidence: float = Field(ge=0, le=1, description="Confidence from 0 to 1.")


class _CategoryResponse(BaseModel):
    categories: list[_CategorySuggestion]


def _serialise_amount(amount: Decimal) -> str:
    return format(abs(amount), "f")


def _build_prompt(items: list[BulkItem], existing_categories: list[str]) -> str:
    transactions = [
        _TransactionInput(
            index=idx,
            name=item.name,
            amount=_serialise_amount(item.amount),
            date=item.date,
            note=item.note,
            current_category=item.category,
        ).model_dump()
        for idx, item in enumerate(items)
    ]
    categories = ", ".join(existing_categories) if existing_categories else "none"
    return (
        "Categorise these personal finance transactions.\n"
        "STRONGLY prefer an existing category from the list below. Reuse the exact "
        "spelling and casing of an existing category whenever it fits, even if it is "
        "a loose fit. Only invent a new category when no existing category could "
        "reasonably apply.\n"
        "Use merchant and note context, ignore dates unless helpful, and never return "
        "empty categories.\n\n"
        f"Existing categories: {categories}\n\n"
        f"Transactions JSON: {json.dumps(transactions, ensure_ascii=False)}"
    )


def _request_body(
    model: str, items: list[BulkItem], existing_categories: list[str]
) -> dict[str, object]:
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "You categorise expense transactions and respond only with valid JSON.",
            },
            {"role": "user", "content": _build_prompt(items, existing_categories)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "transaction_categories",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "categories": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "index": {
                                        "type": "integer",
                                        "description": "Input transaction index.",
                                    },
                                    "category": {
                                        "type": "string",
                                        "description": "Short spending category name.",
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "description": "Confidence from 0 to 1.",
                                    },
                                },
                                "required": ["index", "category", "confidence"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["categories"],
                    "additionalProperties": False,
                },
            },
        },
    }


def _parse_response(payload: object) -> _CategoryResponse:
    if not isinstance(payload, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid response."
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RepositoryError(RepositoryErrorCode.VALIDATION, "OpenRouter returned no choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid choice."
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid message."
        )
    content = message.get("content")
    if not isinstance(content, str) or content.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an empty message."
        )
    try:
        decoded = json.loads(content)
        return _CategoryResponse.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "OpenRouter returned categories in an unexpected format.",
        ) from exc


def _snap_to_existing(suggestion: str, existing_categories: list[str]) -> str:
    cleaned = " ".join(suggestion.split()).lower()
    if not cleaned:
        return suggestion
    for existing in existing_categories:
        if " ".join(existing.split()).lower() == cleaned:
            return existing
    return suggestion


async def categorize_transactions(
    items: list[BulkItem],
    *,
    existing_categories: list[str],
    api_key: str | None,
    model: str,
    client: httpx.AsyncClient | None = None,
) -> CategorizedBulkItems:
    if not items:
        logger.info("ai.categorize.empty")
        return CategorizedBulkItems(items=[], categorized=0)
    if api_key is None or api_key.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "AI categorisation requires QUID_OPENROUTER_API_KEY to be configured.",
        )

    logger.info(
        "ai.categorize.request items=%d model=%s existing_categories=%d",
        len(items),
        model,
        len(existing_categories),
    )
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=60)
    try:
        response = await active_client.post(
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/grant/quid",
                "X-OpenRouter-Title": "Quid",
            },
            json=_request_body(model, items, existing_categories),
        )
    except httpx.HTTPError as exc:
        logger.warning("ai.categorize.http_error err=%s", exc)
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"AI categorisation request failed: {exc}",
        ) from exc
    finally:
        if owns_client:
            await active_client.aclose()

    if response.status_code >= 400:
        logger.warning(
            "ai.categorize.bad_status status=%d body=%r",
            response.status_code,
            response.text[:500],
        )
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"AI categorisation failed with HTTP {response.status_code}.",
        )

    parsed = _parse_response(response.json())
    updates: dict[int, str] = {}
    snapped = 0
    for suggestion in parsed.categories:
        category = suggestion.category.strip()
        if 0 <= suggestion.index < len(items) and category:
            snapped_category = _snap_to_existing(category, existing_categories)
            if snapped_category != category:
                snapped += 1
                logger.debug(
                    "ai.categorize.snap row=%d ai=%r -> existing=%r",
                    suggestion.index,
                    category,
                    snapped_category,
                )
            updates[suggestion.index] = snapped_category

    logger.info(
        "ai.categorize.response items=%d categorised=%d snapped_to_existing=%d",
        len(items),
        len(updates),
        snapped,
    )
    return CategorizedBulkItems(
        items=[
            replace(item, category=updates.get(idx, item.category))
            for idx, item in enumerate(items)
        ],
        categorized=len(updates),
    )
