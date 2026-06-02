from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.expenses import (
    DEFAULT_IMPORTANCE,
    VALID_IMPORTANCE,
    BulkItem,
)

_NAME_ALIASES = ("name", "description", "merchant", "payee")
_AMOUNT_ALIASES = ("amount", "value")
_FEE_ALIASES = ("fee", "fees")
_DATE_ALIASES = (
    "date",
    "started date",
    "completed date",
    "transaction date",
    "posting date",
)
_CATEGORY_ALIASES = ("category", "type", "tag")
_NOTE_ALIASES = ("note", "notes", "memo", "reference")
_STATE_ALIASES = ("state", "status")
_IMPORTANCE_ALIASES = ("importance", "priority")


@dataclass(frozen=True)
class CsvFile:
    filename: str
    content: bytes


@dataclass(frozen=True)
class InvalidRow:
    """A CSV row that could not be imported, with a human-readable reason.

    ``source_row`` is 1-based and counts the header (so the first data row is
    row 2), matching the ``source_row`` used for valid preview rows. The raw
    cell values are captured best-effort so the UI can show the user WHICH row
    was dropped and WHY, instead of only an aggregate count.
    """

    source_row: int
    reason: str
    name: str
    amount: str
    date: str


@dataclass(frozen=True)
class CsvParsed:
    items: list[BulkItem]
    filename: str
    invalid_rows: list[InvalidRow]

    @property
    def skipped_rows(self) -> int:
        return len(self.invalid_rows)


def _normalize_header(value: str) -> str:
    return value.strip().lower()


def _pick_column(header_map: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias in header_map:
            return header_map[alias]
    return None


def _normalize_time(raw: str) -> str:
    """Canonicalise a ``HH:MM[:SS]`` time fragment to ``HH:MM:SS`` or ``""``.

    Returns an empty string for anything that isn't a plain wall-clock time so
    the caller falls back to a date-only value rather than emitting garbage.
    """
    head = raw.strip().split(".", 1)[0]  # drop fractional seconds / tz junk
    head = head.split("+", 1)[0].split("Z", 1)[0].strip()
    parts = head.split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return ""
    hh, mm = parts[0], parts[1]
    ss = parts[2] if len(parts) == 3 else "00"
    if len(hh) != 2 or len(mm) != 2 or len(ss) != 2:
        return ""
    if int(hh) > 23 or int(mm) > 59 or int(ss) > 59:
        return ""
    return f"{hh}:{mm}:{ss}"


def _normalize_date(raw: str) -> str:
    """Return an ISO ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS`` value.

    The time component (after a ``T`` or space separator) is preserved and
    canonicalised when present so that same-day, same-merchant, same-amount
    transactions stay distinct during import dedupe. A bare date stays bare —
    no midnight is fabricated.
    """
    raw = raw.strip()
    if not raw:
        return raw
    if "T" in raw:
        date_part, _, time_part = raw.partition("T")
    elif " " in raw:
        date_part, _, time_part = raw.partition(" ")
    else:
        date_part, time_part = raw, ""

    head = date_part.strip()
    if "/" in head and "-" not in head:
        parts = head.split("/")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            d, m, y = (
                (parts[0], parts[1], parts[2])
                if len(parts[2]) == 4
                else (parts[1], parts[0], parts[2])
            )
            if len(y) == 2:
                y = "20" + y
            head = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    time = _normalize_time(time_part) if time_part else ""
    return f"{head}T{time}" if time else head


def _coerce_amount_string(raw: str) -> str:
    cleaned = raw.strip().replace(",", "").replace("£", "").replace("$", "").replace("€", "")
    return cleaned


def parse_csv(file: CsvFile) -> CsvParsed:
    try:
        text = file.content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"{file.filename}: file is not valid UTF-8 ({exc.reason}).",
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames
    if not fieldnames:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"{file.filename}: CSV is empty or missing a header row.",
        )

    header_map: dict[str, str] = {}
    for field in fieldnames:
        header_map.setdefault(_normalize_header(field), field)

    name_col = _pick_column(header_map, _NAME_ALIASES)
    amount_col = _pick_column(header_map, _AMOUNT_ALIASES)
    fee_col = _pick_column(header_map, _FEE_ALIASES)
    date_col = _pick_column(header_map, _DATE_ALIASES)
    category_col = _pick_column(header_map, _CATEGORY_ALIASES)
    note_col = _pick_column(header_map, _NOTE_ALIASES)
    state_col = _pick_column(header_map, _STATE_ALIASES)
    importance_col = _pick_column(header_map, _IMPORTANCE_ALIASES)

    missing = [
        label
        for label, col in (
            ("name (or description)", name_col),
            ("amount", amount_col),
            ("date (or completed date)", date_col),
        )
        if col is None
    ]
    if missing or name_col is None or amount_col is None or date_col is None:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"{file.filename}: required column(s) missing: {', '.join(missing)}.",
        )

    items: list[BulkItem] = []
    invalid: list[InvalidRow] = []
    # Enumerate from 2 so the reported row number includes the header row,
    # matching the 1-based ``source_row`` used for valid preview rows.
    for source_row, raw in enumerate(reader, start=2):
        name = (raw.get(name_col) or "").strip()
        amount_raw = _coerce_amount_string(raw.get(amount_col) or "")
        fee_raw = _coerce_amount_string(raw.get(fee_col) or "") if fee_col else ""
        date_raw = _normalize_date(raw.get(date_col) or "")
        category = (raw.get(category_col) or "").strip() if category_col else ""
        note = (raw.get(note_col) or "").strip() if note_col else ""

        if state_col is not None:
            state = (raw.get(state_col) or "").strip().upper()
            if state and state != "COMPLETED":
                invalid.append(
                    InvalidRow(
                        source_row,
                        f"Status is “{state}”, not Completed",
                        name,
                        amount_raw,
                        date_raw,
                    )
                )
                continue

        missing = [
            label
            for value, label in ((name, "name"), (amount_raw, "amount"), (date_raw, "date"))
            if not value
        ]
        if missing:
            invalid.append(
                InvalidRow(
                    source_row,
                    f"Missing required value: {', '.join(missing)}",
                    name,
                    amount_raw,
                    date_raw,
                )
            )
            continue

        try:
            amount = Decimal(amount_raw)
        except Exception:
            invalid.append(
                InvalidRow(
                    source_row, f"Amount “{amount_raw}” is not a number", name, amount_raw, date_raw
                )
            )
            continue

        # A non-empty fee column (e.g. Revolut "Premium plan fee") adds to the
        # cost of the transaction. The model is sign-aware here (negative =
        # spend), and a fee always increases what was paid, so subtract its
        # magnitude. This keeps `amount=0.00, fee=7.99` as a 7.99 spend instead
        # of being dropped as "Amount is zero".
        if fee_raw:
            try:
                fee = Decimal(fee_raw)
            except Exception:
                invalid.append(
                    InvalidRow(
                        source_row, f"Fee “{fee_raw}” is not a number", name, amount_raw, date_raw
                    )
                )
                continue
            amount = amount - abs(fee) if amount <= 0 else amount + abs(fee)

        if amount == 0:
            invalid.append(InvalidRow(source_row, "Amount is zero", name, amount_raw, date_raw))
            continue

        importance_raw = (raw.get(importance_col) or "").strip().lower() if importance_col else ""
        importance = importance_raw if importance_raw in VALID_IMPORTANCE else DEFAULT_IMPORTANCE

        items.append(
            BulkItem(
                name=name,
                category=category or "other",
                amount=amount,
                date=date_raw,
                note=note,
                importance=importance,
            )
        )

    return CsvParsed(items=items, filename=file.filename, invalid_rows=invalid)
