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
_DATE_ALIASES = (
    "date",
    "completed date",
    "started date",
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
class CsvParsed:
    items: list[BulkItem]
    filename: str
    skipped_rows: int


def _normalize_header(value: str) -> str:
    return value.strip().lower()


def _pick_column(header_map: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias in header_map:
            return header_map[alias]
    return None


def _normalize_date(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return raw
    head = raw.split("T", 1)[0].split(" ", 1)[0]
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
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return head


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
    skipped = 0
    for raw in reader:
        if state_col is not None:
            state = (raw.get(state_col) or "").strip().upper()
            if state and state != "COMPLETED":
                skipped += 1
                continue

        name = (raw.get(name_col) or "").strip()
        amount_raw = _coerce_amount_string(raw.get(amount_col) or "")
        date_raw = _normalize_date(raw.get(date_col) or "")
        category = (raw.get(category_col) or "").strip() if category_col else ""
        note = (raw.get(note_col) or "").strip() if note_col else ""

        if not name or not amount_raw or not date_raw:
            skipped += 1
            continue

        try:
            amount = Decimal(amount_raw)
        except Exception:
            skipped += 1
            continue

        if amount == 0:
            skipped += 1
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

    return CsvParsed(items=items, filename=file.filename, skipped_rows=skipped)
