"""Shared OpenRouter plumbing: the endpoint, completion parsing, retry policy.

Every AI feature (categorisation, free-form import, Amazon short names,
narratives) posts the same chat-completions shape and reads back the same
``choices[0].message.content`` JSON blob, so the shape checking, the
fence-tolerant JSON extraction and the resample-on-garbage policy live here
once.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

# A malformed completion is a transient model slip, not a permanent failure: the
# same prompt parses on a resample. Retrying beats aborting whatever the user was
# in the middle of.
MAX_PARSE_ATTEMPTS = 2


class UnparseableCompletion(Exception):
    """A completion whose shape we could not read — worth resampling."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message: str = message


def extract_json_object(content: str) -> str:
    # Some providers ignore the json_schema response format and wrap the object
    # in a ```json fence or a sentence of prose. The payload is still there, so
    # pull out the outermost {...} rather than failing the whole call.
    stripped = content.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return stripped
    return stripped[start : end + 1]


def parse_completion[TResponse: BaseModel](
    payload: object,
    response_model: type[TResponse],
    *,
    format_error: str,
    log_prefix: str,
) -> TResponse:
    """Validate an OpenRouter chat completion into ``response_model``.

    Raises ``UnparseableCompletion`` for every deviation so callers can resample
    before surfacing an error to the user.
    """
    if not isinstance(payload, dict):
        raise UnparseableCompletion("OpenRouter returned an invalid response.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise UnparseableCompletion("OpenRouter returned no choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise UnparseableCompletion("OpenRouter returned an invalid choice.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise UnparseableCompletion("OpenRouter returned an invalid message.")
    content = message.get("content")
    if not isinstance(content, str) or content.strip() == "":
        raise UnparseableCompletion("OpenRouter returned an empty message.")
    try:
        return response_model.model_validate(json.loads(extract_json_object(content)))
    except (json.JSONDecodeError, ValidationError) as exc:
        # The raw completion is the only evidence of what actually went wrong
        # (truncation, a fenced blob, an out-of-range field). It holds model
        # output only — no merchant names or amounts from the user's data.
        logger.warning(
            "%s.parse_failed err=%s finish_reason=%r content_len=%d content=%r",
            log_prefix,
            exc,
            first.get("finish_reason"),
            len(content),
            content[:2000],
        )
        raise UnparseableCompletion(format_error) from exc
