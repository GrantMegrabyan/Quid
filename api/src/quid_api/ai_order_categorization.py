"""AI categorisation of Amazon orders.

Reuses the expense categorisation pipeline (same OpenRouter provider/model and
the same category set) so an Amazon order lands in one of the user's existing
spending categories. The order's purchased item titles are the primary signal:
they go in the transaction ``note`` (the prompt leans on note context), with a
short label as the ``name``.

The resulting category NAME is resolved to a category id via the shared
``ExpenseRepository.resolve_or_create_category`` helper, so an order can create
a ``cat-<slug>`` category exactly like an expense import would when no existing
category fits.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from quid_api.ai_categorization import categorize_transactions
from quid_api.repositories.amazon_orders import deserialize_items
from quid_api.repositories.expenses import BulkItem, ExpenseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import AmazonOrder, Category

logger = logging.getLogger(__name__)


def _order_titles(order: AmazonOrder) -> list[str]:
    return [str(item["title"]) for item in deserialize_items(order.items_json) if item.get("title")]


def _order_to_item(order: AmazonOrder, titles: list[str]) -> BulkItem:
    label = order.short_name or (titles[0] if titles else "")
    note = "; ".join(titles)
    return BulkItem(
        name=label or "Amazon order",
        category="",
        amount=order.total if isinstance(order.total, Decimal) else Decimal(str(order.total)),
        date=order.order_date,
        note=note,
    )


async def categorize_amazon_orders(
    session: AsyncSession,
    orders: list[AmazonOrder],
    *,
    existing_categories: list[tuple[str, str]],
    ai_rules: list[str],
    api_key: str | None,
    model: str,
    chunk_size: int,
) -> dict[str, str]:
    """Return ``{order_id: category_id}`` for orders with usable item titles.

    Orders with no usable titles are skipped (we have nothing to categorise on
    and would otherwise force the model to guess from amount/date alone).
    """
    eligible: list[AmazonOrder] = []
    items: list[BulkItem] = []
    for order in orders:
        titles = _order_titles(order)
        if not titles and not order.short_name:
            continue
        eligible.append(order)
        items.append(_order_to_item(order, titles))
    if not items:
        return {}

    categorized = await categorize_transactions(
        items,
        existing_categories=existing_categories,
        ai_rules=ai_rules,
        api_key=api_key,
        model=model,
        chunk_size=chunk_size,
    )

    expense_repo = ExpenseRepository(session)
    created_index: dict[str, Category] = {}
    result: dict[str, str] = {}
    for order, item in zip(eligible, categorized.items, strict=True):
        category = await expense_repo.resolve_or_create_category(item.category, created_index)
        result[order.id] = category.id
    logger.info(
        "amazon.categorize.done orders=%d categorized=%d",
        len(eligible),
        len(result),
    )
    return result


async def suggest_amazon_order_categories(
    orders: list[AmazonOrder],
    *,
    existing_categories: list[tuple[str, str]],
    ai_rules: list[str],
    api_key: str | None,
    model: str,
    chunk_size: int,
) -> dict[str, str]:
    """Return ``{order_id: suggested_category_name}`` WITHOUT persisting anything.

    The read-only sibling of :func:`categorize_amazon_orders`: it runs the same
    AI categorisation (so a re-categorise preview reflects the current AI rules
    and category set) but yields the raw suggested category NAME instead of
    resolving/creating a category id. The caller (the re-categorise preview
    endpoint) decides what to show and only writes on confirm. Orders with no
    usable item titles or short name are skipped (nothing to categorise on).
    """
    eligible: list[AmazonOrder] = []
    items: list[BulkItem] = []
    for order in orders:
        titles = _order_titles(order)
        if not titles and not order.short_name:
            continue
        eligible.append(order)
        items.append(_order_to_item(order, titles))
    if not items:
        return {}

    categorized = await categorize_transactions(
        items,
        existing_categories=existing_categories,
        ai_rules=ai_rules,
        api_key=api_key,
        model=model,
        chunk_size=chunk_size,
    )

    result: dict[str, str] = {}
    for order, item in zip(eligible, categorized.items, strict=True):
        name = (item.category or "").strip()
        if name:
            result[order.id] = name
    logger.info(
        "amazon.recategorize.preview orders=%d suggested=%d",
        len(eligible),
        len(result),
    )
    return result
