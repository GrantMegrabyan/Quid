"""Shared calendar-date validation/normalization for ``YYYY-MM-DD`` strings.

Quid stores transaction dates as ``YYYY-MM-DD`` text (see ``models.py``). Inputs
historically only had their *shape* checked with a regex
(``^\\d{4}-\\d{2}-\\d{2}$``), which happily accepted pattern-valid-but-impossible
dates like ``2026-13-40`` or ``2025-02-29``. Those would be persisted and then
silently never match anything sensible.

This module centralises real calendar validation via ``date.fromisoformat`` so
every input seam (expenses, bulk import, Amazon orders, import preview/confirm,
import rules, test seed) agrees on what a valid date is.

Two flavours:

- ``validate_iso_date`` — strict. Returns the normalised string or raises
  ``ValueError``. Use where a bad value is a hard error (API request fields,
  repository writes).
- ``normalize_iso_date`` — lenient. Returns the normalised string or ``None``.
  Use where a bad value should be SKIPPED rather than rejected (browser-export
  ingest, which drops just the offending order).

``date.fromisoformat`` (Python 3.11+) accepts the full ISO-8601 grammar,
including separators we don't want (``2026-W01-1``, ``20260401``). We therefore
keep a strict ``YYYY-MM-DD`` shape gate in front of it so the contract is
exactly "four-digit year, two-digit month, two-digit day, real calendar date".
"""

from __future__ import annotations

import re
from datetime import date

#: Strict ``YYYY-MM-DD`` shape. ``date.fromisoformat`` would also accept basic
#: (``20260401``) and week-date forms, which are not part of our wire contract.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_iso_date(value: str) -> str | None:
    """Return ``value`` as a validated ``YYYY-MM-DD`` string, or ``None``.

    Trims surrounding whitespace. Returns ``None`` for any value that is not a
    real ``YYYY-MM-DD`` calendar date (wrong shape, impossible month/day, or an
    extended ISO form we don't accept). Callers that want to *skip* bad input
    use this; callers that want to *reject* use ``validate_iso_date``.
    """
    candidate = value.strip() if value is not None else ""
    if not _ISO_DATE_RE.match(candidate):
        return None
    try:
        date.fromisoformat(candidate)
    except ValueError:
        return None
    return candidate


def validate_iso_date(value: str) -> str:
    """Return ``value`` as a validated ``YYYY-MM-DD`` string or raise.

    Raises ``ValueError`` (with a stable message) when the value is not a real
    calendar date. The repository layer wraps this in a ``RepositoryError``;
    Pydantic surfaces it directly as a 422.
    """
    normalized = normalize_iso_date(value)
    if normalized is None:
        raise ValueError(f"Date must be a valid YYYY-MM-DD calendar date, got {value!r}")
    return normalized
