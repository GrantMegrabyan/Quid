from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from quid_api.errors import RepositoryError, RepositoryErrorCode

if TYPE_CHECKING:
    from decimal import Decimal

    from quid_api.repositories.expenses import BulkItem

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_CHUNK_SIZE = 25


@dataclass(frozen=True)
class CategorizedBulkItems:
    items: list[BulkItem]
    categorized: int
    excluded_indices: frozenset[int] = field(default_factory=frozenset)


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
    exclude: bool = Field(description="True when AI rules say this transaction should be excluded.")
    confidence: float = Field(ge=0, le=1, description="Confidence from 0 to 1.")


class _CategoryResponse(BaseModel):
    categories: list[_CategorySuggestion]


def _serialise_amount(amount: Decimal) -> str:
    return format(abs(amount), "f")


def _format_categories(existing_categories: list[tuple[str, str]]) -> str:
    if not existing_categories:
        return "none"
    lines = []
    for name, description in existing_categories:
        if description:
            lines.append(f"- {name}: {description}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _format_prior_decisions(prior_decisions: dict[str, str]) -> str:
    if not prior_decisions:
        return "none"
    return "\n".join(
        f"- {name} -> {category}" for name, category in sorted(prior_decisions.items())
    )


def _build_prompt(
    items: list[BulkItem],
    existing_categories: list[tuple[str, str]],
    ai_rules: list[str],
    prior_decisions: dict[str, str],
) -> str:
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
    categories_block = _format_categories(existing_categories)
    rules = "\n".join(f"- {rule}" for rule in ai_rules) if ai_rules else "- none"
    prior_block = _format_prior_decisions(prior_decisions)
    return (
        "Categorise these personal finance transactions.\n"
        "Before categorising, apply the AI rules below. If a transaction should be "
        "excluded, set exclude=true and still provide the best category.\n\n"
        f"AI rules:\n{rules}\n\n"
        "STRONGLY prefer an existing category from the list below. Reuse the exact "
        "spelling and casing of an existing category whenever it fits, even if it is "
        "a loose fit. Use the category descriptions to decide which category fits best. "
        "Only invent a new category when no existing category could reasonably apply.\n"
        "Use merchant and note context, ignore dates unless helpful, and never return "
        "empty categories.\n\n"
        f"Existing categories:\n{categories_block}\n\n"
        "Decisions made earlier in this same import (prefer the same category when the "
        "same merchant appears again, unless context clearly differs):\n"
        f"{prior_block}\n\n"
        f"Transactions JSON: {json.dumps(transactions, ensure_ascii=False)}"
    )


def _request_body(
    model: str,
    items: list[BulkItem],
    existing_categories: list[tuple[str, str]],
    ai_rules: list[str],
    prior_decisions: dict[str, str],
) -> dict[str, object]:
    prompt = _build_prompt(items, existing_categories, ai_rules, prior_decisions)
    prompt_without_transactions = prompt.split("Transactions JSON:", 1)[0]
    logger.debug(
        "ai.categorize.prompt model=%s items=%d prior_decisions=%d prompt=%r "
        "transactions=<%d transactions redacted>",
        model,
        len(items),
        len(prior_decisions),
        prompt_without_transactions + "Transactions JSON: <transactions redacted>",
        len(items),
    )
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "You categorise expense transactions and respond only with valid JSON.",
            },
            {"role": "user", "content": prompt},
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
                                    "exclude": {
                                        "type": "boolean",
                                        "description": "Whether AI rules say to exclude this transaction.",
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "description": "Confidence from 0 to 1.",
                                    },
                                },
                                "required": ["index", "category", "exclude", "confidence"],
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


def _snap_to_existing(suggestion: str, existing_categories: list[tuple[str, str]]) -> str:
    cleaned = " ".join(suggestion.split()).lower()
    if not cleaned:
        return suggestion
    for name, _ in existing_categories:
        if " ".join(name.split()).lower() == cleaned:
            return name
    return suggestion


async def _categorize_chunk(
    chunk: list[BulkItem],
    *,
    existing_categories: list[tuple[str, str]],
    ai_rules: list[str],
    prior_decisions: dict[str, str],
    api_key: str,
    model: str,
    client: httpx.AsyncClient,
) -> _CategoryResponse:
    body = _request_body(model, chunk, existing_categories, ai_rules, prior_decisions)
    try:
        response = await client.post(
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/grant/quid",
                "X-OpenRouter-Title": "Quid",
            },
            json=body,
        )
    except httpx.HTTPError as exc:
        logger.warning("ai.categorize.http_error err=%s", exc)
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"AI categorisation request failed: {exc}",
        ) from exc

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

    return _parse_response(response.json())


async def categorize_transactions(
    items: list[BulkItem],
    *,
    existing_categories: list[tuple[str, str]],
    ai_rules: list[str] | None = None,
    api_key: str | None,
    model: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
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

    effective_chunk_size = max(1, chunk_size)
    total_chunks = (len(items) + effective_chunk_size - 1) // effective_chunk_size
    logger.info(
        "ai.categorize.request items=%d chunks=%d chunk_size=%d model=%s existing_categories=%d",
        len(items),
        total_chunks,
        effective_chunk_size,
        model,
        len(existing_categories),
    )

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=60)

    updates: dict[int, str] = {}
    excluded: set[int] = set()
    # Sequential, not parallel: each chunk's prompt includes decisions made in
    # earlier chunks so the model stays consistent on naming and repeat merchants.
    # Parallelising would defeat this carry-over, which is the point of chunking.
    running_decisions: dict[str, str] = {}
    snapped_total = 0
    effective_rules = ai_rules or []

    try:
        for chunk_number, chunk_start in enumerate(
            range(0, len(items), effective_chunk_size), start=1
        ):
            chunk = items[chunk_start : chunk_start + effective_chunk_size]
            parsed = await _categorize_chunk(
                chunk,
                existing_categories=existing_categories,
                ai_rules=effective_rules,
                prior_decisions=running_decisions,
                api_key=api_key,
                model=model,
                client=active_client,
            )

            chunk_categorized = 0
            chunk_excluded = 0
            for suggestion in parsed.categories:
                category = suggestion.category.strip()
                if not (0 <= suggestion.index < len(chunk)) or not category:
                    continue
                global_index = chunk_start + suggestion.index
                if suggestion.exclude:
                    excluded.add(global_index)
                    chunk_excluded += 1
                snapped = _snap_to_existing(category, existing_categories)
                if snapped != category:
                    snapped_total += 1
                    logger.debug(
                        "ai.categorize.snap row=%d ai=%r -> existing=%r",
                        global_index,
                        category,
                        snapped,
                    )
                updates[global_index] = snapped
                chunk_categorized += 1
                running_decisions[chunk[suggestion.index].name] = snapped

            logger.info(
                "ai.categorize.chunk chunk=%d/%d items=%d categorized=%d excluded=%d",
                chunk_number,
                total_chunks,
                len(chunk),
                chunk_categorized,
                chunk_excluded,
            )
    finally:
        if owns_client:
            await active_client.aclose()

    logger.info(
        "ai.categorize.response items=%d chunks=%d categorised=%d snapped_to_existing=%d excluded=%d",
        len(items),
        total_chunks,
        len(updates),
        snapped_total,
        len(excluded),
    )
    return CategorizedBulkItems(
        items=[
            replace(item, category=updates.get(idx, item.category))
            for idx, item in enumerate(items)
        ],
        categorized=len(updates),
        excluded_indices=frozenset(excluded),
    )
