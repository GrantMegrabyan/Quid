from __future__ import annotations

import contextlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import combinations
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import AmazonOrder, Category, Expense, ExpenseAmazonOrderLink

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_amazon_merchant() -> ColumnElement[bool]:
    """SQL predicate matching expenses whose merchant name looks like Amazon.

    There is no dedicated merchant column; the merchant is stored in
    ``Expense.name`` (e.g. "Amazon Mktp", "AMZN Mktp", "AMZ*1A2B3C"). We
    match the common Amazon descriptor stems case-insensitively. Auto-match
    and suggestions are additionally gated by amount + date, so this only
    narrows candidates; manual linking is unaffected.
    """
    name = func.lower(Expense.name)
    return or_(name.like("%amazon%"), name.like("%amzn%"), name.like("%amz%"))


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
    # Of the auto-matched count, how many came from the combined-order pass
    # (i.e. multiple orders linked to a single expense). Surfaces the new
    # behaviour without breaking the existing two-field response.
    combined_matched: int = 0


# Pass 2 (combined orders) safeguards. Tuned for Amazon's billing behaviour:
# orders that ship/bill together do so within a tight date cluster (≤2
# days between order dates, expense within ±3 days of the latest).
#
# The min-total threshold is a coincidence guard for very small sums; the
# stronger guard is uniqueness — a combo only links if it's the unique
# (combo, expense) match. £5 catches small same-day pairs (e.g. nappies +
# toothpaste billed together) while still rejecting trivial £0.99 + £1.50
# coincidences.
_COMBINED_ORDER_DATE_SPAN_DAYS = 2
_COMBINED_EXPENSE_WINDOW_DAYS = 3
_COMBINED_MIN_TOTAL = Decimal("5")
_COMBINED_MAX_SIZE = 3

# An Amazon order's category may overwrite an expense's category only when the
# expense category came from a low-priority guess. A 'manual' (user-edited),
# 'rule' (import-rule), or existing 'amazon' category is never overwritten.
_OVERRIDABLE_CATEGORY_SOURCES = frozenset({"import", "ai"})


def _expense_accepts_inherited_category(expense: Expense) -> bool:
    return expense.category_source in _OVERRIDABLE_CATEGORY_SOURCES


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

        # Re-importing keeps an existing short_name: it may have been edited by
        # the user, and we only generate one once at first import.

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

    async def set_generated_short_names(self, names: dict[str, str]) -> None:
        """Store AI-generated short names, only for orders that don't yet have
        one. Never overwrites an existing (possibly user-edited) value."""
        for order_id, short_name in names.items():
            order = await self.session.get(AmazonOrder, order_id)
            if order is None or order.short_name:
                continue
            order.short_name = short_name
        await self.session.flush()

    async def update_short_name(self, order_id: str, short_name: str) -> AmazonOrder:
        order = await self.get(order_id)
        cleaned = " ".join(short_name.split())
        order.short_name = cleaned or None
        await self.session.flush()
        return order

    async def set_order_category(self, order_id: str, category_id: str | None) -> AmazonOrder:
        """Set (or clear, with ``None``) an order's category explicitly, then
        push it onto linked ``ai``/``import`` expenses. Validates the category
        exists. Unlike AI generation this overwrites any existing order
        category, because the user is choosing it deliberately."""
        order = await self.get(order_id)
        if category_id is not None:
            category = await self.session.get(Category, category_id)
            if category is None:
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    f'Category "{category_id}" does not exist.',
                )
        order.category_id = category_id
        if category_id is not None:
            await self._propagate_category_to_links(order)
        await self.session.flush()
        return order

    async def set_generated_categories(self, categories: dict[str, str]) -> int:
        """Store AI-derived category ids on orders that don't yet have one.

        Never overwrites an existing category (mirrors short names). After
        setting an order's category, propagate it to any already-linked
        uncategorised expenses so a backfill / re-import actually benefits
        the orders that were auto-matched at their first import.

        Returns the number of orders that received a category.
        """
        named = 0
        for order_id, category_id in categories.items():
            if not category_id:
                continue
            order = await self.session.get(AmazonOrder, order_id)
            if order is None or order.category_id:
                continue
            order.category_id = category_id
            named += 1
            await self._propagate_category_to_links(order)
        await self.session.flush()
        return named

    async def propagate_all_categories_to_links(self) -> int:
        """Push every categorised order's category onto its linked expenses
        that still carry a low-priority category (``import``/``ai``).

        This is the standalone cleanup pass: ``set_generated_categories`` only
        propagates for orders it newly categorises, so orders that already had
        a category (e.g. categorised at import while their linked expense was
        an AI ``Shopping`` guess) would never be reconciled without this.
        Idempotent and safe to re-run. Returns the number of expenses changed.
        """
        changed = 0
        for order in await self.list_all():
            if not order.category_id:
                continue
            changed += await self._propagate_category_to_links(order)
        await self.session.flush()
        return changed

    async def _propagate_category_to_links(self, order: AmazonOrder) -> int:
        """Push the order's category onto each linked expense whose category
        came from a low-priority guess (``import`` default or expense ``ai``).
        Hand-set (``manual``), import-rule (``rule``), and already-inherited
        (``amazon``) categories are never overwritten. Returns the number of
        expenses changed."""
        if not order.category_id:
            return 0
        changed = 0
        expense_ids = await self.linked_expense_ids(order.id)
        for expense_id in expense_ids:
            expense = await self.session.get(Expense, expense_id)
            if expense is None or not _expense_accepts_inherited_category(expense):
                continue
            expense.category_id = order.category_id
            expense.category_source = "amazon"
            changed += 1
        return changed

    async def _linked_expense_ids_set(self) -> set[str]:
        rows = (await self.session.scalars(select(ExpenseAmazonOrderLink.expense_id))).all()
        return set(rows)

    def _charge_amounts(self, order: AmazonOrder) -> list[tuple[Decimal, date | None]]:
        """Amounts that could plausibly match a single bank charge for this
        order: always the order total at order_date; additionally each
        shipment total at its ship_date when the order has more than one
        shipment (Amazon may bill those separately)."""
        charges: list[tuple[Decimal, date | None]] = [(order.total, None)]
        shipments = deserialize_shipments(order.shipments_json)
        if len(shipments) > 1:
            for ship in shipments:
                total = ship.get("total")
                if not isinstance(total, Decimal) or total <= 0 or total == order.total:
                    continue
                ship_date: date | None = None
                raw_date = ship.get("ship_date")
                if isinstance(raw_date, str) and raw_date:
                    try:
                        ship_date = _parse_date(raw_date)
                    except ValueError:
                        ship_date = None
                charges.append((total, ship_date))
        return charges

    async def suggest_matches(self, order_id: str, *, window_days: int = 7) -> list[Expense]:
        """Unlinked expenses that match the order total or any shipment
        total, within ``window_days`` of the order date (or the shipment's
        ship date when shipment-level)."""
        order = await self.get(order_id)
        order_date = _parse_date(order.order_date)
        linked_expense_ids = await self._linked_expense_ids_set()
        charges = self._charge_amounts(order)
        amounts = {amount for amount, _ in charges}
        rows = list(
            (
                await self.session.scalars(
                    select(Expense)
                    .where(Expense.amount.in_(amounts))
                    .where(_is_amazon_merchant())
                    .order_by(Expense.date.desc(), Expense.id)
                )
            ).all()
        )
        seen: set[str] = set()
        matches: list[Expense] = []
        for candidate in rows:
            if candidate.id in linked_expense_ids or candidate.id in seen:
                continue
            try:
                candidate_date = _parse_date(candidate.date)
            except ValueError:
                continue
            for amount, expected_date in charges:
                if candidate.amount != amount:
                    continue
                target = expected_date or order_date
                if abs((candidate_date - target).days) <= window_days:
                    matches.append(candidate)
                    seen.add(candidate.id)
                    break
        return matches

    async def linked_expense_ids(self, order_id: str) -> list[str]:
        rows = (
            await self.session.scalars(
                select(ExpenseAmazonOrderLink.expense_id)
                .where(ExpenseAmazonOrderLink.amazon_order_id == order_id)
                .order_by(ExpenseAmazonOrderLink.expense_id)
            )
        ).all()
        return list(rows)

    async def linked_map(self, order_ids: list[str]) -> dict[str, list[str]]:
        if not order_ids:
            return {}
        rows = (
            await self.session.execute(
                select(
                    ExpenseAmazonOrderLink.amazon_order_id,
                    ExpenseAmazonOrderLink.expense_id,
                )
                .where(ExpenseAmazonOrderLink.amazon_order_id.in_(order_ids))
                .order_by(ExpenseAmazonOrderLink.expense_id)
            )
        ).all()
        result: dict[str, list[str]] = {oid: [] for oid in order_ids}
        for amazon_order_id, expense_id in rows:
            result.setdefault(amazon_order_id, []).append(expense_id)
        return result

    async def expense_linked_orders(self, expense_ids: list[str]) -> dict[str, list[str]]:
        """For each expense id, return the Amazon orders it is linked to."""
        if not expense_ids:
            return {}
        rows = (
            await self.session.execute(
                select(
                    ExpenseAmazonOrderLink.expense_id,
                    ExpenseAmazonOrderLink.amazon_order_id,
                )
                .where(ExpenseAmazonOrderLink.expense_id.in_(expense_ids))
                .order_by(ExpenseAmazonOrderLink.amazon_order_id)
            )
        ).all()
        result: dict[str, list[str]] = {eid: [] for eid in expense_ids}
        for expense_id, amazon_order_id in rows:
            result.setdefault(expense_id, []).append(amazon_order_id)
        return result

    async def _link_pair(
        self, order_id: str, expense_id: str, *, inherit_category: bool = True
    ) -> None:
        existing = await self.session.get(ExpenseAmazonOrderLink, (expense_id, order_id))
        if existing is not None:
            return
        self.session.add(ExpenseAmazonOrderLink(expense_id=expense_id, amazon_order_id=order_id))
        if inherit_category:
            await self._inherit_category_on_link(order_id, expense_id)

    async def _inherit_category_on_link(self, order_id: str, expense_id: str) -> None:
        """When a single order links to an expense, the expense inherits the
        order's (precise) category when its own category came from a
        low-priority guess (``import`` default or expense ``ai``). A
        hand-set (``manual``) or import-rule (``rule``) category is never
        overwritten."""
        order = await self.session.get(AmazonOrder, order_id)
        if order is None or not order.category_id:
            return
        expense = await self.session.get(Expense, expense_id)
        if expense is None or not _expense_accepts_inherited_category(expense):
            return
        expense.category_id = order.category_id
        expense.category_source = "amazon"

    async def link_expense(self, order_id: str, expense_id: str) -> Expense:
        order = await self.get(order_id)
        expense = await self.session.get(Expense, expense_id)
        if expense is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Expense not found: {expense_id}",
            )
        await self._link_pair(order.id, expense.id)
        await self.session.flush()
        return expense

    async def unlink_expense(self, order_id: str, expense_id: str) -> Expense:
        expense = await self.session.get(Expense, expense_id)
        if expense is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Expense not found: {expense_id}",
            )
        link = await self.session.get(ExpenseAmazonOrderLink, (expense_id, order_id))
        if link is None:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Expense is not linked to this Amazon order.",
            )
        await self.session.delete(link)
        await self.session.flush()
        return expense

    async def auto_match_all(self, *, window_days: int = 7) -> AutoMatchResult:
        """Two-pass linker that ignores already-linked orders and expenses.

        Pass 1 — per-order: link each unlinked order to the sole unlinked
        expense whose amount equals the order total OR (for multi-shipment
        orders) any shipment total, within ``window_days`` of the relevant
        date. Orders are processed fewest-candidates-first so a unique
        match isn't accidentally consumed by an ambiguous one.

        Pass 2 — combined orders: for orders still unlinked, look for tight
        date clusters (≤2 days between order dates) of 2..3 orders whose
        summed total uniquely matches an unlinked expense within ±3 days
        of the latest order date and whose total exceeds ``£5``. Same
        ``payment_last4`` is required when known for both sides. Ambiguous
        combos (two combos matching the same expense, or one combo with
        multiple candidate expenses) are skipped.

        Idempotent: re-running never disturbs existing links.
        """
        orders = await self.list_all()
        total_orders = len(orders)
        existing_links = await self.linked_map([order.id for order in orders])
        unlinked_orders = [order for order in orders if not existing_links.get(order.id)]

        used_expense_ids: set[str] = set()
        auto_matched = 0
        ambiguous = 0

        # --- Pass 1: per-order ----------------------------------------------
        # Sort orders by candidate count so uniquely-resolvable ones claim
        # their expense before contested ones do. After each successful link
        # we re-collect candidates because a now-consumed expense may have
        # disambiguated other orders.
        candidates_by_order = {
            o.id: await self.suggest_matches(o.id, window_days=window_days) for o in unlinked_orders
        }
        pending = {o.id: o for o in unlinked_orders}
        progress = True
        while progress:
            progress = False
            ordered = sorted(
                pending.values(),
                key=lambda o: (
                    len([c for c in candidates_by_order[o.id] if c.id not in used_expense_ids])
                    or 9_999,
                    o.order_date,
                    o.id,
                ),
            )
            for order in ordered:
                fresh = [c for c in candidates_by_order[order.id] if c.id not in used_expense_ids]
                if len(fresh) == 1:
                    await self._link_pair(order.id, fresh[0].id)
                    used_expense_ids.add(fresh[0].id)
                    auto_matched += 1
                    pending.pop(order.id, None)
                    progress = True

        still_unmatched = list(pending.values())

        # --- Pass 2: combined orders ----------------------------------------
        combined_matched, _ = await self._run_combined_pass(still_unmatched, used_expense_ids)
        auto_matched += combined_matched
        # Orders still unlinked after both passes are "ambiguous" — either
        # no candidate found, or genuine ambiguity remained.
        linked_after = await self.linked_map([o.id for o in unlinked_orders])
        ambiguous = sum(1 for o in unlinked_orders if not linked_after.get(o.id))

        await self.session.flush()
        return AutoMatchResult(
            auto_matched=auto_matched,
            ambiguous=ambiguous,
            total_orders=total_orders,
            combined_matched=combined_matched,
        )

    async def _run_combined_pass(
        self,
        unmatched_orders: list[AmazonOrder],
        used_expense_ids: set[str],
    ) -> tuple[int, int]:
        """Try summing 2..N nearby unmatched orders to find a unique expense.

        Returns ``(linked_orders, skipped_ambiguous_combos)``.
        """
        if len(unmatched_orders) < 2:
            return 0, 0

        # Pre-fetch candidate expenses whose amount equals the sum of any
        # plausible combo. Cheap upper bound: amount must be at least
        # _COMBINED_MIN_TOTAL. We pull all unlinked expenses ≥ threshold and
        # filter by amount equality + date window in Python.
        rows = (
            await self.session.scalars(
                select(Expense)
                .where(Expense.amount >= _COMBINED_MIN_TOTAL)
                .where(_is_amazon_merchant())
                .order_by(Expense.date)
            )
        ).all()
        candidate_expenses: list[Expense] = []
        for e in rows:
            if e.id in used_expense_ids:
                continue
            try:
                _parse_date(e.date)
            except ValueError:
                continue
            candidate_expenses.append(e)
        if not candidate_expenses:
            return 0, 0

        # Index expenses by amount for O(1) lookup.
        by_amount: dict[Decimal, list[Expense]] = defaultdict(list)
        for e in candidate_expenses:
            by_amount[e.amount].append(e)

        # Build the universe of combos that pass all safeguards.
        combos: list[tuple[tuple[AmazonOrder, ...], Decimal, date]] = []
        parsed_dates: dict[str, date] = {}
        for o in unmatched_orders:
            with contextlib.suppress(ValueError):
                parsed_dates[o.id] = _parse_date(o.order_date)
        eligible = [o for o in unmatched_orders if o.id in parsed_dates]

        eligible.sort(key=lambda o: (parsed_dates[o.id], o.id))
        for start, first in enumerate(eligible):
            window: list[AmazonOrder] = [first]
            first_date = parsed_dates[first.id]
            for other in eligible[start + 1 :]:
                if (parsed_dates[other.id] - first_date).days > _COMBINED_ORDER_DATE_SPAN_DAYS:
                    break
                window.append(other)
            for size in range(2, _COMBINED_MAX_SIZE + 1):
                if len(window) < size:
                    break
                for combo in combinations(window, size):
                    dates = [parsed_dates[o.id] for o in combo]
                    last4s = {o.payment_last4 for o in combo if o.payment_last4}
                    if len(last4s) > 1:
                        # Mixed payment methods → almost certainly distinct charges.
                        continue
                    total = sum((o.total for o in combo), Decimal(0))
                    if total < _COMBINED_MIN_TOTAL:
                        continue
                    combos.append((combo, total, max(dates)))

        # For each combo, find matching expenses within the expense window.
        combo_matches: list[tuple[tuple[AmazonOrder, ...], Decimal, date, Expense]] = []
        for combo, total, anchor_date in combos:
            for expense in by_amount.get(total, []):
                if expense.id in used_expense_ids:
                    continue
                edate = _parse_date(expense.date)
                if abs((edate - anchor_date).days) > _COMBINED_EXPENSE_WINDOW_DAYS:
                    continue
                # Payment-last4 alignment when both sides have it.
                combo_last4 = next((o.payment_last4 for o in combo if o.payment_last4), None)
                # We don't currently carry payment_last4 on Expense rows, so
                # this is informational only — left here as a hook for when
                # we do, without changing match outcomes.
                _ = combo_last4
                combo_matches.append((combo, total, anchor_date, expense))

        # Reject when the same expense matches multiple distinct combos
        # (genuine ambiguity), and when a combo matches multiple expenses.
        expense_to_combos: dict[str, list[tuple[AmazonOrder, ...]]] = defaultdict(list)
        combo_to_expenses: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for combo, _total, _anchor, expense in combo_matches:
            combo_key = tuple(o.id for o in combo)
            expense_to_combos[expense.id].append(combo)
            combo_to_expenses[combo_key].append(expense.id)

        # Deterministic ordering: smallest date span first, then lex by ids.
        def _combo_key(c: tuple[AmazonOrder, ...]) -> tuple[int, str]:
            dates = sorted(parsed_dates[o.id] for o in c)
            span = (dates[-1] - dates[0]).days
            return (span, ",".join(sorted(o.id for o in c)))

        linked_count = 0
        ambiguous_count = 0
        # Sort combo_matches so we resolve the tightest, lex-smallest first.
        combo_matches.sort(key=lambda m: (_combo_key(m[0]), m[3].date, m[3].id))

        consumed_order_ids: set[str] = set()
        for combo, _total, _anchor, expense in combo_matches:
            combo_key = tuple(sorted(o.id for o in combo))
            if expense.id in used_expense_ids:
                continue
            # Multiple expenses match this combo → ambiguous, skip.
            if len(set(combo_to_expenses[combo_key])) > 1:
                ambiguous_count += 1
                continue
            # Multiple combos match this expense → ambiguous, skip.
            if len({tuple(sorted(o.id for o in c)) for c in expense_to_combos[expense.id]}) > 1:
                ambiguous_count += 1
                continue
            # Any participant already consumed by an earlier successful link.
            if any(o.id in consumed_order_ids for o in combo):
                continue
            # Combined charge spans multiple orders: the expense only inherits
            # a category when every participating order agrees on it
            # (unanimous-or-skip). Picking one of several differing categories
            # would be lossy, so we leave the expense as-is otherwise.
            combo_categories = {o.category_id for o in combo if o.category_id}
            shared_category = next(iter(combo_categories)) if len(combo_categories) == 1 else None
            for o in combo:
                await self._link_pair(o.id, expense.id, inherit_category=False)
                consumed_order_ids.add(o.id)
            if shared_category is not None and _expense_accepts_inherited_category(expense):
                expense.category_id = shared_category
                expense.category_source = "amazon"
            used_expense_ids.add(expense.id)
            linked_count += len(combo)

        return linked_count, ambiguous_count
