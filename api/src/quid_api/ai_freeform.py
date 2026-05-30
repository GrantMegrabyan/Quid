"""AI parsing of free-form transaction text into structured expense items.

Reuses the same OpenRouter provider/model as expense categorisation. Given a
multi-line block of free-form text (e.g. "coffee 3.50 yesterday, tesco 42 on
the 3rd"), it extracts a list of transactions with a name, amount, ISO date and
optional note. Category/importance assignment is left to the existing
``categorize_transactions`` pass, which runs afterwards.

Used by the Import page's "AI free-form" tab. The raw input and the extracted
rows are recorded in the import log so a user can see what was parsed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import BaseModel, ValidationError

from quid_api.ai_categorization import OPENROUTER_CHAT_COMPLETIONS_URL
from quid_api.errors import RepositoryError, RepositoryErrorCode

logger = logging.getLogger(__name__)

# Hard cap so a pasted wall of text can't blow up a single prompt.
MAX_INPUT_CHARS = 10_000


@dataclass(frozen=True)
class ParsedFreeformItem:
    name: str
    amount: str
    date: str
    note: str


class _FreeformSuggestion(BaseModel):
    name: str
    # The model is instructed to return amount as a plain decimal STRING
    # ("3.50"); parsing to Decimal happens server-side so we never route money
    # through a float. A numeric value is still tolerated (coerced via str())
    # in case the model ignores the instruction.
    amount: str
    date: str
    note: str = ""


class _FreeformResponse(BaseModel):
    transactions: list[_FreeformSuggestion]


def _build_prompt(text: str, today: str) -> str:
    return (
        "Extract personal-finance transactions from the free-form text below. "
        "Each line or clause may describe one purchase/expense.\n\n"
        "Rules:\n"
        "- Output one entry per distinct transaction you can identify.\n"
        "- name: the merchant or short description (e.g. 'Tesco', 'Coffee').\n"
        "- amount: the positive amount paid, as a plain decimal STRING with at "
        'most two fractional digits (e.g. "3.50", "42"). No currency symbol, '
        "no thousands separators, no sign. Ignore any sign; treat all as "
        "spending.\n"
        f"- date: resolve to an ISO date (YYYY-MM-DD). Today is {today}. "
        "Resolve relative dates like 'yesterday', 'last friday', 'the 3rd' "
        "against today. If no date is given, use today.\n"
        "- note: any extra detail that is not the merchant name; empty string "
        "if none.\n"
        "- Do NOT assign a category; that happens later.\n"
        "- Skip lines that clearly are not transactions.\n\n"
        f"Text:\n{text}"
    )


def _request_body(model: str, text: str, today: str) -> dict[str, object]:
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract structured expense transactions from free-form "
                    "text and respond only with valid JSON."
                ),
            },
            {"role": "user", "content": _build_prompt(text, today)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "freeform_transactions",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "transactions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Merchant or short description.",
                                    },
                                    "amount": {
                                        "type": "string",
                                        "description": (
                                            'Positive amount paid as a decimal string, e.g. "3.50".'
                                        ),
                                    },
                                    "date": {
                                        "type": "string",
                                        "description": "ISO date YYYY-MM-DD.",
                                    },
                                    "note": {
                                        "type": "string",
                                        "description": "Extra detail or empty string.",
                                    },
                                },
                                "required": ["name", "amount", "date", "note"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["transactions"],
                    "additionalProperties": False,
                },
            },
        },
    }


def _parse_response(payload: object) -> _FreeformResponse:
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
        return _FreeformResponse.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "OpenRouter returned transactions in an unexpected format.",
        ) from exc


async def parse_freeform_transactions(
    text: str,
    *,
    api_key: str | None,
    model: str,
    today: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[ParsedFreeformItem]:
    """Parse free-form text into a list of transaction items via OpenRouter.

    Raises ``RepositoryError`` when the API key is missing, the text is empty,
    or the AI call fails. Amount/date validation is left to the import preview
    pipeline so malformed rows surface in the same place as CSV ones.
    """
    cleaned = text.strip()
    if not cleaned:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Enter some transaction text to parse.",
        )
    if len(cleaned) > MAX_INPUT_CHARS:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"Input is too long (max {MAX_INPUT_CHARS} characters).",
        )
    if api_key is None or api_key.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "AI free-form import requires QUID_OPENROUTER_API_KEY to be configured.",
        )

    effective_today = today or datetime.now(UTC).date().isoformat()
    body = _request_body(model, cleaned, effective_today)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=60)
    logger.info("ai.freeform.request chars=%d model=%s", len(cleaned), model)
    try:
        try:
            response = await active_client.post(
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
            logger.warning("ai.freeform.http_error err=%s", exc)
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"AI free-form parsing request failed: {exc}",
            ) from exc
        if response.status_code >= 400:
            logger.warning(
                "ai.freeform.bad_status status=%d body=%r",
                response.status_code,
                response.text[:500],
            )
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"AI free-form parsing failed with HTTP {response.status_code}.",
            )
        parsed = _parse_response(response.json())
    finally:
        if owns_client:
            await active_client.aclose()

    items = [
        item
        for suggestion in parsed.transactions
        if suggestion.name.strip() and (item := _to_item(suggestion)) is not None
    ]
    logger.info("ai.freeform.done extracted=%d model=%s", len(items), model)
    return items


def _to_item(suggestion: _FreeformSuggestion) -> ParsedFreeformItem | None:
    """Build a parsed item, parsing the model's string amount via Decimal.

    Amounts are parsed server-side with ``Decimal`` (never ``float``) so money
    keeps its exact value. A row whose amount can't be parsed is dropped here
    rather than poisoning the downstream preview with garbage; the remaining
    good rows still import. The amount is emitted as a canonical absolute
    decimal string for the preview pipeline (which validates 2dp itself).
    """
    raw = suggestion.amount.strip()
    try:
        amount = abs(Decimal(raw))
    except (InvalidOperation, ValueError):
        logger.warning("ai.freeform.bad_amount amount=%r name=%r", raw, suggestion.name)
        return None
    return ParsedFreeformItem(
        name=suggestion.name.strip(),
        amount=format(amount, "f"),
        date=suggestion.date.strip(),
        note=suggestion.note.strip(),
    )
