"""AI narrative for the Analytics page.

Takes a compact JSON facts payload (the same aggregates the page renders:
verdict numbers, top increases with contributing merchants, detector findings,
recurring-stack total) and asks OpenRouter for a short plain-language summary.
Strictly on-demand — callers decide when to spend the API call.
"""

from __future__ import annotations

import logging

import httpx

from quid_api.ai_categorization import OPENROUTER_CHAT_COMPLETIONS_URL
from quid_api.errors import RepositoryError, RepositoryErrorCode

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a personal-finance analyst. You write short, plain-language "
    "summaries of a single month's spending. Respond with prose only — no "
    "markdown, no headings, no bullet points."
)


def _build_prompt(facts_json: str) -> str:
    return (
        "Summarise this month's spending for the user in 3-6 sentences.\n\n"
        "Rules:\n"
        "- Name the biggest driver of any change vs the user's average.\n"
        "- Point at the most concrete saving opportunities in the data "
        "(price increases, new subscriptions, habit spend), with their costs.\n"
        "- Use ONLY numbers present in the data below; never invent figures.\n"
        "- Currency amounts are plain decimals; present them naturally.\n"
        "- Address the user as 'you'.\n\n"
        f"Data (JSON):\n{facts_json}"
    )


async def generate_narrative(
    facts_json: str,
    *,
    api_key: str | None,
    model: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Generate the narrative text via OpenRouter.

    Raises ``RepositoryError`` (VALIDATION) when the key is missing or the
    call fails, mirroring ``ai_freeform.parse_freeform_transactions``.
    """
    if api_key is None or api_key.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "AI insights require QUID_OPENROUTER_API_KEY to be configured.",
        )

    body = {
        "model": model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(facts_json)},
        ],
    }
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=60)
    logger.info("ai.narrative.request model=%s chars=%d", model, len(facts_json))
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
            logger.warning("ai.narrative.http_error err=%s", exc)
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"AI narrative request failed: {exc}",
            ) from exc
        if response.status_code >= 400:
            logger.warning(
                "ai.narrative.bad_status status=%d body=%r",
                response.status_code,
                response.text[:500],
            )
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"AI narrative generation failed with HTTP {response.status_code}.",
            )
        payload = response.json()
    finally:
        if owns_client:
            await active_client.aclose()

    content = _extract_content(payload)
    logger.info("ai.narrative.done chars=%d model=%s", len(content), model)
    return content


def _extract_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid response."
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RepositoryError(RepositoryErrorCode.VALIDATION, "OpenRouter returned no choices.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid message."
        )
    content = message.get("content")
    if not isinstance(content, str) or content.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an empty message."
        )
    return content.strip()
