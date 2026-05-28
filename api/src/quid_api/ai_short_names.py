"""AI generation of brief, human-readable names for Amazon orders.

Reuses the same OpenRouter provider/model as expense categorisation. Given an
order's purchased item titles, it produces a single short label (<= 60 chars)
describing what was bought, e.g. "USB-C cables + phone case".

Generated once at import time and stored on the order; never regenerated
implicitly. The user may override the stored value.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

from quid_api.ai_categorization import OPENROUTER_CHAT_COMPLETIONS_URL
from quid_api.errors import RepositoryError, RepositoryErrorCode

logger = logging.getLogger(__name__)

MAX_SHORT_NAME_LENGTH = 60
DEFAULT_CHUNK_SIZE = 25


@dataclass(frozen=True)
class ShortNameInput:
    order_id: str
    item_titles: list[str]


class _ShortNameSuggestion(BaseModel):
    index: int
    short_name: str


class _ShortNameResponse(BaseModel):
    names: list[_ShortNameSuggestion]


def _truncate(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= MAX_SHORT_NAME_LENGTH:
        return cleaned
    return cleaned[: MAX_SHORT_NAME_LENGTH - 1].rstrip() + "\u2026"


def _fallback(order: ShortNameInput) -> str:
    titles = [t for t in (title.strip() for title in order.item_titles) if t]
    if not titles:
        return ""
    first = titles[0]
    if len(titles) == 1:
        return _truncate(first)
    return _truncate(f"{first} + {len(titles) - 1} more")


def _build_prompt(chunk: list[ShortNameInput]) -> str:
    orders = [
        {"index": idx, "items": [t for t in order.item_titles if t.strip()]}
        for idx, order in enumerate(chunk)
    ]
    return (
        "For each Amazon order below, write ONE very brief plain-language label "
        "describing what was purchased. Rules:\n"
        f"- Maximum {MAX_SHORT_NAME_LENGTH} characters.\n"
        "- Summarise the items; do not just copy a long product title verbatim.\n"
        "- When several distinct items, summarise concisely "
        '(e.g. "USB-C cables + phone case").\n'
        "- No quotes, no trailing punctuation, no order ids.\n"
        "- Return one entry per input index.\n\n"
        f"Orders JSON: {json.dumps(orders, ensure_ascii=False)}"
    )


def _request_body(model: str, chunk: list[ShortNameInput]) -> dict[str, object]:
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write short product purchase summaries and respond only with valid JSON."
                ),
            },
            {"role": "user", "content": _build_prompt(chunk)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "amazon_short_names",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "names": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "index": {
                                        "type": "integer",
                                        "description": "Input order index.",
                                    },
                                    "short_name": {
                                        "type": "string",
                                        "description": ("Brief description of what was purchased."),
                                    },
                                },
                                "required": ["index", "short_name"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["names"],
                    "additionalProperties": False,
                },
            },
        },
    }


def _parse_response(payload: object) -> _ShortNameResponse:
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
        return _ShortNameResponse.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "OpenRouter returned short names in an unexpected format.",
        ) from exc


async def _short_names_chunk(
    chunk: list[ShortNameInput],
    *,
    api_key: str,
    model: str,
    client: httpx.AsyncClient,
) -> _ShortNameResponse:
    body = _request_body(model, chunk)
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
    if response.status_code >= 400:
        logger.warning(
            "ai.short_names.bad_status status=%d body=%r",
            response.status_code,
            response.text[:500],
        )
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"AI short-name generation failed with HTTP {response.status_code}.",
        )
    return _parse_response(response.json())


async def generate_short_names(
    orders: list[ShortNameInput],
    *,
    api_key: str | None,
    model: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    """Return a map of order_id -> short name for the given orders.

    When the API key is missing or the AI call fails, falls back to a simple
    title-based label so import still succeeds with a usable value. Orders
    with no item titles are omitted from the result.
    """
    populated = [o for o in orders if any(t.strip() for t in o.item_titles)]
    if not populated:
        return {}

    if api_key is None or api_key.strip() == "":
        logger.info("ai.short_names.no_api_key fallback orders=%d", len(populated))
        return {o.order_id: name for o in populated if (name := _fallback(o))}

    effective_chunk_size = max(1, chunk_size)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=60)

    result: dict[str, str] = {}
    try:
        for chunk_start in range(0, len(populated), effective_chunk_size):
            chunk = populated[chunk_start : chunk_start + effective_chunk_size]
            try:
                parsed = await _short_names_chunk(
                    chunk, api_key=api_key, model=model, client=active_client
                )
            except (RepositoryError, httpx.HTTPError) as exc:
                logger.warning("ai.short_names.chunk_failed err=%s fallback", exc)
                for order in chunk:
                    fallback = _fallback(order)
                    if fallback:
                        result[order.order_id] = fallback
                continue
            seen: set[int] = set()
            for suggestion in parsed.names:
                if not (0 <= suggestion.index < len(chunk)):
                    continue
                seen.add(suggestion.index)
                order = chunk[suggestion.index]
                name = _truncate(suggestion.short_name) or _fallback(order)
                if name:
                    result[order.order_id] = name
            for idx, order in enumerate(chunk):
                if idx in seen:
                    continue
                fallback = _fallback(order)
                if fallback:
                    result[order.order_id] = fallback
    finally:
        if owns_client:
            await active_client.aclose()

    logger.info(
        "ai.short_names.done orders=%d named=%d model=%s",
        len(populated),
        len(result),
        model,
    )
    return result
