from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from quid_api.errors import RepositoryError, RepositoryErrorCode

_ORDER_ID_ALIASES = (
    "order id",
    "order_id",
    "orderid",
    "amazon order id",
    "amazon order #",
)
_ORDER_DATE_ALIASES = (
    "order date",
    "purchase date",
    "orderdate",
    "date",
)
_TOTAL_ALIASES = (
    "total owed",
    "total charged",
    "totalamount",
    "total amount",
    "total",
    "order total",
    "amount",
    "grand total",
)
_CURRENCY_ALIASES = ("currency", "currency code")
_TITLE_ALIASES = (
    "product name",
    "title",
    "item title",
    "item name",
)
_QUANTITY_ALIASES = ("quantity", "qty", "item qty")
_ITEM_PRICE_ALIASES = (
    "item subtotal",
    "item total",
    "item price",
    "price",
    "unit price",
)
_LAST4_ALIASES = (
    "last 4 digits",
    "last4",
    "payment last4",
    "payment instrument last 4",
)
_STATUS_ALIASES = ("order status", "status")
_ORDER_URL_ALIASES = ("order url", "url", "link")
_ITEMS_BLOB_ALIASES = ("items",)

_ACCEPTED_STATUSES: frozenset[str] = frozenset(
    {"", "closed", "shipped", "delivered", "complete", "completed"}
)


@dataclass(frozen=True)
class AmazonCsvFile:
    filename: str
    content: bytes


@dataclass(frozen=True)
class AmazonParsedItem:
    title: str
    quantity: int = 1
    price: Decimal | None = None


@dataclass
class AmazonParsedOrder:
    order_id: str
    order_date: str
    total: Decimal
    currency: str = "GBP"
    items: list[AmazonParsedItem] = field(default_factory=list)
    payment_last4: str | None = None
    order_url: str | None = None


@dataclass(frozen=True)
class AmazonCsvParsed:
    orders: list[AmazonParsedOrder]
    filename: str
    skipped_rows: int


def _normalize_header(value: str) -> str:
    return value.strip().lower()


def _pick_column(header_map: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias in header_map:
            return header_map[alias]
    return None


def _coerce_amount_string(raw: str) -> str:
    return (
        raw.strip()
        .replace(",", "")
        .replace("£", "")
        .replace("$", "")
        .replace("€", "")
        .replace("USD", "")
        .replace("GBP", "")
        .replace("EUR", "")
        .strip()
    )


def _parse_decimal(raw: str) -> Decimal | None:
    cleaned = _coerce_amount_string(raw)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
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


def _coerce_int(raw: str, fallback: int = 1) -> int:
    cleaned = raw.strip()
    if not cleaned:
        return fallback
    try:
        return max(1, int(Decimal(cleaned)))
    except (InvalidOperation, ValueError):
        return fallback


def _extract_last4(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.findall(r"\d{4}", raw)
    return digits[-1] if digits else None


def _parse_items_blob(blob: str) -> list[AmazonParsedItem]:
    cleaned = blob.strip()
    if not cleaned:
        return []
    if cleaned.startswith("["):
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return _parse_items_delimited(cleaned)
        items: list[AmazonParsedItem] = []
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    title = str(entry.get("title") or entry.get("name") or "").strip()
                    if not title:
                        continue
                    quantity = _coerce_int(str(entry.get("quantity") or entry.get("qty") or "1"))
                    price_raw = entry.get("price") or entry.get("amount")
                    price = _parse_decimal(str(price_raw)) if price_raw is not None else None
                    items.append(AmazonParsedItem(title=title, quantity=quantity, price=price))
        return items
    return _parse_items_delimited(cleaned)


def _parse_items_delimited(blob: str) -> list[AmazonParsedItem]:
    items: list[AmazonParsedItem] = []
    for chunk in blob.split(";"):
        title = chunk.strip()
        if title:
            items.append(AmazonParsedItem(title=title))
    return items


def parse_amazon_csv(file: AmazonCsvFile, default_currency: str = "GBP") -> AmazonCsvParsed:
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
    for field_name in fieldnames:
        header_map.setdefault(_normalize_header(field_name), field_name)

    order_id_col = _pick_column(header_map, _ORDER_ID_ALIASES)
    order_date_col = _pick_column(header_map, _ORDER_DATE_ALIASES)
    total_col = _pick_column(header_map, _TOTAL_ALIASES)
    currency_col = _pick_column(header_map, _CURRENCY_ALIASES)
    title_col = _pick_column(header_map, _TITLE_ALIASES)
    quantity_col = _pick_column(header_map, _QUANTITY_ALIASES)
    item_price_col = _pick_column(header_map, _ITEM_PRICE_ALIASES)
    last4_col = _pick_column(header_map, _LAST4_ALIASES)
    status_col = _pick_column(header_map, _STATUS_ALIASES)
    order_url_col = _pick_column(header_map, _ORDER_URL_ALIASES)
    items_blob_col = _pick_column(header_map, _ITEMS_BLOB_ALIASES)

    if order_id_col is None or order_date_col is None or total_col is None:
        missing = [
            label
            for label, col in (
                ("order id", order_id_col),
                ("order date", order_date_col),
                ("total", total_col),
            )
            if col is None
        ]
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"{file.filename}: required column(s) missing: {', '.join(missing)}.",
        )

    by_id: dict[str, AmazonParsedOrder] = {}
    skipped = 0

    for raw in reader:
        if status_col is not None:
            status = (raw.get(status_col) or "").strip().lower()
            if status and status not in _ACCEPTED_STATUSES:
                skipped += 1
                continue

        order_id = (raw.get(order_id_col) or "").strip()
        order_date = _normalize_date(raw.get(order_date_col) or "")
        total = _parse_decimal(raw.get(total_col) or "")
        if not order_id or not order_date or total is None or total <= 0:
            skipped += 1
            continue

        currency = (
            (raw.get(currency_col) or "").strip().upper() if currency_col else ""
        ) or default_currency.upper()
        last4 = _extract_last4(raw.get(last4_col) or "") if last4_col else None
        order_url = (raw.get(order_url_col) or "").strip() if order_url_col else None
        order_url = order_url or None

        existing = by_id.get(order_id)
        if existing is None:
            existing = AmazonParsedOrder(
                order_id=order_id,
                order_date=order_date,
                total=total,
                currency=currency,
                payment_last4=last4,
                order_url=order_url,
            )
            by_id[order_id] = existing
        else:
            if existing.total <= 0 and total > 0:
                existing.total = total
            if last4 and not existing.payment_last4:
                existing.payment_last4 = last4
            if order_url and not existing.order_url:
                existing.order_url = order_url

        if items_blob_col is not None:
            blob = raw.get(items_blob_col) or ""
            for parsed_item in _parse_items_blob(blob):
                existing.items.append(parsed_item)

        if title_col is not None:
            title = (raw.get(title_col) or "").strip()
            if title:
                quantity = _coerce_int(raw.get(quantity_col) or "1") if quantity_col else 1
                price = _parse_decimal(raw.get(item_price_col) or "") if item_price_col else None
                existing.items.append(AmazonParsedItem(title=title, quantity=quantity, price=price))

    return AmazonCsvParsed(
        orders=list(by_id.values()),
        filename=file.filename,
        skipped_rows=skipped,
    )
