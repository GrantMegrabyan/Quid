from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import AmazonOrder, Expense

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


@dataclass(frozen=True)
class ParsedShipmentInput:
    total: Decimal
    ship_date: str | None = None
    tracking: str | None = None
    items: list[dict[str, object]] | None = None


@dataclass(frozen=True)
class ParsedOrderInput:
    order_id: str
    order_date: str
    total: Decimal
    currency: str = "GBP"
    items: list[dict[str, object]] | None = None
    shipments: list[ParsedShipmentInput] | None = None
    payment_last4: str | None = None
    order_url: str | None = None


@dataclass(frozen=True)
class BulkUpsertResult:
    created: int
    updated: int


@dataclass(frozen=True)
class AutoMatchResult:
    auto_matched: int
    ambiguous: int
    total_orders: int


def serialize_items(items: list[dict[str, object]] | None) -> str:
    if not items:
        return "[]"
    serializable: list[dict[str, object]] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        quantity_raw = item.get("quantity")
        try:
            quantity = max(1, int(str(quantity_raw))) if quantity_raw is not None else 1
        except (TypeError, ValueError):
            quantity = 1
        price = item.get("price")
        price_str: str | None = None if price is None or price == "" else str(price)
        serializable.append({"title": title, "quantity": quantity, "price": price_str})
    return json.dumps(serializable)


def serialize_shipments(shipments: list[ParsedShipmentInput] | None) -> str:
    if not shipments:
        return "[]"
    payload = [
        {
            "ship_date": s.ship_date,
            "tracking": s.tracking,
            "total": str(s.total),
            "items": json.loads(serialize_items(s.items)),
        }
        for s in shipments
    ]
    return json.dumps(payload)


def deserialize_shipments(shipments_json: str) -> list[dict[str, object]]:
    raw = json.loads(shipments_json or "[]")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, object]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        total_value = entry.get("total")
        try:
            total = Decimal(str(total_value)) if total_value is not None else Decimal(0)
        except Exception:
            total = Decimal(0)
        result.append(
            {
                "ship_date": entry.get("ship_date") or None,
                "tracking": entry.get("tracking") or None,
                "total": total,
                "items": entry.get("items") or [],
            }
        )
    return result


def deserialize_items(items_json: str) -> list[dict[str, object]]:
    raw = json.loads(items_json or "[]")
    result: list[dict[str, object]] = []
    if not isinstance(raw, list):
        return result
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        quantity_value = entry.get("quantity")
        try:
            quantity = max(1, int(quantity_value)) if quantity_value is not None else 1
        except (TypeError, ValueError):
            quantity = 1
        price_value = entry.get("price")
        price: Decimal | None
        if price_value is None or price_value == "":
            price = None
        else:
            try:
                price = Decimal(str(price_value))
            except Exception:
                price = None
        result.append({"title": title, "quantity": quantity, "price": price})
    return result


class AmazonOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[AmazonOrder]:
        result = await self.session.scalars(
            select(AmazonOrder).order_by(AmazonOrder.order_date.desc(), AmazonOrder.id)
        )
        return list(result.all())

    async def get(self, order_id: str) -> AmazonOrder:
        row = await self.session.get(AmazonOrder, order_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Amazon order not found: {order_id}",
            )
        return row

    async def upsert(self, payload: ParsedOrderInput) -> tuple[AmazonOrder, bool]:
        existing = await self.session.get(AmazonOrder, payload.order_id)
        now = _now_iso()
        items_blob = serialize_items(payload.items)
        shipments_blob = serialize_shipments(payload.shipments)
        if existing is None:
            row = AmazonOrder(
                id=payload.order_id,
                order_date=payload.order_date,
                total=payload.total,
                currency=payload.currency,
                items_json=items_blob,
                shipments_json=shipments_blob,
                payment_last4=payload.payment_last4,
                order_url=payload.order_url,
                imported_at=now,
            )
            self.session.add(row)
            await self.session.flush()
            return row, True

        existing.order_date = payload.order_date
        existing.total = payload.total
        existing.currency = payload.currency
        existing.items_json = items_blob
        existing.shipments_json = shipments_blob
        existing.payment_last4 = payload.payment_last4 or existing.payment_last4
        existing.order_url = payload.order_url or existing.order_url
        existing.imported_at = now
        await self.session.flush()
        return existing, False

    async def bulk_upsert(self, payloads: list[ParsedOrderInput]) -> BulkUpsertResult:
        created = 0
        updated = 0
        for payload in payloads:
            _, was_created = await self.upsert(payload)
            if was_created:
                created += 1
            else:
                updated += 1
        return BulkUpsertResult(created=created, updated=updated)

    async def delete(self, order_id: str) -> None:
        row = await self.session.get(AmazonOrder, order_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Amazon order not found: {order_id}",
            )
        await self.session.delete(row)
        await self.session.flush()

    async def suggest_matches(self, order_id: str, *, window_days: int = 7) -> list[Expense]:
        order = await self.get(order_id)
        order_date = _parse_date(order.order_date)
        candidates = list(
            (
                await self.session.scalars(
                    select(Expense)
                    .where(
                        Expense.amount == order.total,
                        Expense.amazon_order_id.is_(None),
                    )
                    .order_by(Expense.date.desc(), Expense.id)
                )
            ).all()
        )
        matches: list[Expense] = []
        for candidate in candidates:
            try:
                candidate_date = _parse_date(candidate.date)
            except ValueError:
                continue
            if abs((candidate_date - order_date).days) <= window_days:
                matches.append(candidate)
        return matches

    async def linked_expense_ids(self, order_id: str) -> list[str]:
        rows = (
            await self.session.scalars(
                select(Expense.id).where(Expense.amazon_order_id == order_id).order_by(Expense.id)
            )
        ).all()
        return list(rows)

    async def linked_map(self, order_ids: list[str]) -> dict[str, list[str]]:
        if not order_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Expense.amazon_order_id, Expense.id)
                .where(Expense.amazon_order_id.in_(order_ids))
                .order_by(Expense.id)
            )
        ).all()
        result: dict[str, list[str]] = {oid: [] for oid in order_ids}
        for amazon_order_id, expense_id in rows:
            if amazon_order_id is None:
                continue
            result.setdefault(amazon_order_id, []).append(expense_id)
        return result

    async def link_expense(self, order_id: str, expense_id: str) -> Expense:
        order = await self.get(order_id)
        expense = await self.session.get(Expense, expense_id)
        if expense is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Expense not found: {expense_id}",
            )
        if expense.amazon_order_id and expense.amazon_order_id != order.id:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Expense is already linked to a different Amazon order.",
            )
        expense.amazon_order_id = order.id
        await self.session.flush()
        return expense

    async def unlink_expense(self, order_id: str, expense_id: str) -> Expense:
        expense = await self.session.get(Expense, expense_id)
        if expense is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Expense not found: {expense_id}",
            )
        if expense.amazon_order_id != order_id:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Expense is not linked to this Amazon order.",
            )
        expense.amazon_order_id = None
        await self.session.flush()
        return expense

    async def auto_match_all(self, *, window_days: int = 7) -> AutoMatchResult:
        """For each order with no linked expense, link it to the SOLE unlinked
        expense candidate whose amount matches the order total and whose date
        falls within ``window_days`` of the order date. Orders with zero or
        multiple candidates are counted as ambiguous and skipped.
        """
        orders = await self.list_all()
        total_orders = len(orders)
        existing_links = await self.linked_map([order.id for order in orders])
        unlinked_orders = [order for order in orders if not existing_links.get(order.id)]

        auto_matched = 0
        ambiguous = 0
        used_expense_ids: set[str] = set()
        for order in unlinked_orders:
            candidates = await self.suggest_matches(order.id, window_days=window_days)
            fresh = [c for c in candidates if c.id not in used_expense_ids]
            if len(fresh) == 1:
                fresh[0].amazon_order_id = order.id
                used_expense_ids.add(fresh[0].id)
                auto_matched += 1
            else:
                ambiguous += 1
        await self.session.flush()
        return AutoMatchResult(
            auto_matched=auto_matched,
            ambiguous=ambiguous,
            total_orders=total_orders,
        )
