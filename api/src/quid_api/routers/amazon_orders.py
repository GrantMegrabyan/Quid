from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import select

from quid_api.ai_order_categorization import (
    categorize_amazon_orders,
    suggest_amazon_order_categories,
)
from quid_api.ai_short_names import ShortNameInput, generate_short_names
from quid_api.amazon_csv_import import (
    _ACCEPTED_STATUSES,
    AmazonCsvFile,
    _normalize_date,
    _parse_decimal,
    parse_amazon_csv,
)
from quid_api.category_helpers import slugify_category, titleize_slug
from quid_api.datelib import normalize_iso_date
from quid_api.db import get_session
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category
from quid_api.repositories.ai_rules import AiRuleRepository
from quid_api.repositories.amazon_orders import (
    AmazonOrderRepository,
    ParsedOrderInput,
    ParsedShipmentInput,
    deserialize_items,
    deserialize_shipments,
)
from quid_api.repositories.app_settings import AppSettingsRepository
from quid_api.repositories.expenses import ExpenseRepository
from quid_api.schemas import (
    AmazonCategoryRequest,
    AmazonExportOrder,
    AmazonExportRequest,
    AmazonImportFileReport,
    AmazonImportResponse,
    AmazonImportSkippedOrder,
    AmazonLinkedExpense,
    AmazonLinkRequest,
    AmazonMatchAllResponse,
    AmazonOrderItem,
    AmazonOrderListOut,
    AmazonOrderOut,
    AmazonOrderShipment,
    AmazonRecategorizeConfirmRequest,
    AmazonRecategorizeConfirmResponse,
    AmazonRecategorizePreviewResponse,
    AmazonRecategorizePreviewRow,
    AmazonShortNameRequest,
    CategorySource,
    ExpenseOut,
    Importance,
)
from quid_api.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import AmazonOrder, Expense

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/amazon-orders", tags=["amazon-orders"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@dataclass(frozen=True)
class _IngestResult:
    created: int
    updated: int
    auto_matched: int
    ambiguous: int
    combined_matched: int


def _order_to_out(
    order: AmazonOrder,
    linked_expense_ids: list[str],
    linked_expenses: list[AmazonLinkedExpense] | None = None,
) -> AmazonOrderOut:
    items_data = deserialize_items(order.items_json)
    items = [
        AmazonOrderItem(
            title=cast("str", item["title"]),
            quantity=cast("int", item["quantity"]),
            price=item["price"],  # type: ignore[arg-type]
        )
        for item in items_data
    ]
    shipments_data = deserialize_shipments(order.shipments_json)
    shipments = [
        AmazonOrderShipment(
            ship_date=cast("str | None", shipment.get("ship_date")),
            tracking=cast("str | None", shipment.get("tracking")),
            total=shipment["total"],  # type: ignore[arg-type]
            items=[
                AmazonOrderItem(
                    title=cast("str", item["title"]),
                    quantity=cast("int", item.get("quantity") or 1),
                    price=item.get("price"),  # type: ignore[arg-type]
                )
                for item in cast("list[dict[str, object]]", shipment.get("items") or [])
            ],
        )
        for shipment in shipments_data
    ]
    return AmazonOrderOut(
        id=order.id,
        order_date=order.order_date,
        total=order.total,
        currency=order.currency,
        items=items,
        shipments=shipments,
        payment_last4=order.payment_last4,
        order_url=order.order_url,
        short_name=order.short_name,
        category_id=order.category_id,
        imported_at=order.imported_at,
        linked_expense_ids=linked_expense_ids,
        linked_expenses=linked_expenses or [],
    )


@router.get("", response_model=AmazonOrderListOut)
async def list_amazon_orders(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    linked: Annotated[bool | None, Query()] = None,
    category_id: Annotated[str | None, Query(alias="categoryId")] = None,
    search: Annotated[str | None, Query()] = None,
) -> AmazonOrderListOut:
    """List Amazon orders, paginated and filterable.

    - ``limit``/``offset`` page the result (never fetch the whole table).
    - ``linked`` filters to linked (``true``) or not-linked (``false``) orders.
    - ``categoryId`` filters by category; ``""`` / ``uncategorized`` means
      "orders with no category".
    - ``search`` is a case-insensitive substring over the order id, short name,
      and item titles.
    """
    repo = AmazonOrderRepository(session)
    orders, total = await repo.list_paginated(
        limit=limit,
        offset=offset,
        linked=linked,
        category_id=category_id,
        search=search,
    )
    links = await repo.linked_map([order.id for order in orders])
    # Resolve every linked expense id (across this page only) once, so the page
    # can render "Linked to ..." labels without fetching the whole expense table.
    linked_ids = {eid for ids in links.values() for eid in ids}
    expense_repo = ExpenseRepository(session)
    expenses = await expense_repo.get_many(list(linked_ids))
    label_by_id = {
        e.id: AmazonLinkedExpense(
            id=e.id,
            name=e.name,
            amount=e.amount,
            display_name=e.display_name,
        )
        for e in expenses
    }
    items: list[AmazonOrderOut] = []
    for order in orders:
        ids = links.get(order.id, [])
        labels = [label_by_id[eid] for eid in ids if eid in label_by_id]
        items.append(_order_to_out(order, ids, labels))
    return AmazonOrderListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=AmazonOrderOut)
async def get_amazon_order(order_id: str, session: SessionDep) -> AmazonOrderOut:
    repo = AmazonOrderRepository(session)
    order = await repo.get(order_id)
    linked = await repo.linked_expense_ids(order.id)
    return _order_to_out(order, linked)


@router.post(
    "/import-csv",
    response_model=AmazonImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_amazon_csv(
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="Amazon order export CSV files.")],
) -> AmazonImportResponse:
    if not files:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "At least one CSV file is required.",
        )

    settings_repo = AppSettingsRepository(session)
    settings_row = await settings_repo.get()
    default_currency = settings_row.currency

    all_orders: list[ParsedOrderInput] = []
    reports: list[AmazonImportFileReport] = []
    for upload in files:
        content = await upload.read()
        filename = upload.filename or "amazon.csv"
        parsed = parse_amazon_csv(
            AmazonCsvFile(filename=filename, content=content),
            default_currency=default_currency,
        )
        payloads = [
            ParsedOrderInput(
                order_id=order.order_id,
                order_date=order.order_date,
                total=order.total,
                currency=order.currency,
                items=[
                    {
                        "title": item.title,
                        "quantity": item.quantity,
                        "price": item.price,
                    }
                    for item in order.items
                ],
                shipments=[
                    ParsedShipmentInput(
                        ship_date=shipment.ship_date,
                        tracking=shipment.tracking,
                        total=shipment.total,
                        items=[
                            {
                                "title": item.title,
                                "quantity": item.quantity,
                                "price": item.price,
                            }
                            for item in shipment.items
                        ],
                    )
                    for shipment in order.shipments
                ],
                payment_last4=order.payment_last4,
                order_url=order.order_url,
            )
            for order in parsed.orders
        ]
        all_orders.extend(payloads)
        reports.append(
            AmazonImportFileReport(
                filename=filename,
                orders_parsed=len(parsed.orders),
                skipped_rows=parsed.skipped_rows,
            )
        )
    result = await _ingest_orders(session, all_orders, source="csv")
    return AmazonImportResponse(
        created=result.created,
        updated=result.updated,
        auto_matched=result.auto_matched,
        ambiguous=result.ambiguous,
        combined_matched=result.combined_matched,
        files=reports,
    )


async def _ingest_orders(
    session: AsyncSession,
    parsed_orders: list[ParsedOrderInput],
    *,
    source: str,
) -> _IngestResult:
    repo = AmazonOrderRepository(session)
    settings_repo = AppSettingsRepository(session)
    settings_row = await settings_repo.get()
    settings = get_settings()
    result = await repo.bulk_upsert(parsed_orders)
    # Item titles per order id so we can generate short names once after upsert.
    titles_by_order: dict[str, list[str]] = {}
    for order in parsed_orders:
        titles_by_order[order.order_id] = [cast("str", item["title"]) for item in order.items or []]

    if settings_row.ai_short_names_enabled:
        needs_name: list[ShortNameInput] = []
        for order_id, titles in titles_by_order.items():
            existing = await repo.get(order_id)
            if existing.short_name:
                continue
            needs_name.append(ShortNameInput(order_id=order_id, item_titles=titles))
        if needs_name:
            try:
                generated = await generate_short_names(
                    needs_name,
                    api_key=settings.openrouter_api_key,
                    model=settings.openrouter_model,
                    chunk_size=settings.openrouter_chunk_size,
                )
                await repo.set_generated_short_names(generated)
            except RepositoryError:
                logger.warning("amazon.import.short_names_failed", exc_info=True)

    if settings_row.ai_categorize_enabled:
        uncategorized = []
        for order_id in titles_by_order:
            imported_order = await repo.get(order_id)
            if imported_order.category_id is None:
                uncategorized.append(imported_order)
        if uncategorized:
            try:
                category_rows = list(
                    await session.execute(
                        select(Category.name, Category.description).order_by(Category.name)
                    )
                )
                ai_rules = [
                    rule.text
                    for rule in await AiRuleRepository(session).list_all(enabled_only=True)
                ]
                derived = await categorize_amazon_orders(
                    session,
                    uncategorized,
                    existing_categories=[(row.name, row.description) for row in category_rows],
                    ai_rules=ai_rules,
                    api_key=settings.openrouter_api_key,
                    model=settings_row.categorize_model or settings.openrouter_model,
                    chunk_size=settings.openrouter_chunk_size,
                )
                await repo.set_generated_categories(derived)
            except RepositoryError:
                logger.warning("amazon.import.categorize_failed", exc_info=True)

    match_result = await repo.auto_match_all()
    await session.commit()
    logger.info(
        "amazon.ingest source=%s created=%d updated=%d auto_matched=%d ambiguous=%d combined_matched=%d",
        source,
        result.created,
        result.updated,
        match_result.auto_matched,
        match_result.ambiguous,
        match_result.combined_matched,
    )
    return _IngestResult(
        created=result.created,
        updated=result.updated,
        auto_matched=match_result.auto_matched,
        ambiguous=match_result.ambiguous,
        combined_matched=match_result.combined_matched,
    )


def _normalized_iso_date(raw: str) -> str | None:
    """Normalise an export ``order_date`` and re-assert the ``AmazonOrder``
    date CHECK (``models.py``) IN CODE.

    Returns the ``YYYY-MM-DD`` string, or ``None`` when the value can't be
    normalised to a real ISO calendar date. ``_normalize_date`` first coerces
    the scraper's looser inputs (``/`` separators, trailing time) to the
    ``YYYY-MM-DD`` shape; ``normalize_iso_date`` then enforces the strict shape
    AND real-calendar-date contract (rejecting e.g. ``2026-13-40`` or
    ``2025-02-29``) so a bad value is SKIPPED here rather than stored and
    silently never matched.
    """
    return normalize_iso_date(_normalize_date(raw))


@router.post(
    "/import-export",
    response_model=AmazonImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_amazon_export(
    session: SessionDep, payload: AmazonExportRequest
) -> AmazonImportResponse:
    """Ingest browser-scraped Amazon orders (see ``AmazonExportRequest``).

    Mirrors the CSV importer's validation policy: structural problems are 422s
    (Pydantic handles body shape; ``orders`` min-length handles an empty list),
    while row-level problems (blank order id, non-importable status,
    unparseable date, missing/non-positive total) are SKIPPED per-order with a
    reason and reported back, so a partial scrape still imports its good
    orders. Surviving orders feed the SAME ``_ingest_orders`` pipeline as CSV.
    """
    settings_repo = AppSettingsRepository(session)
    settings_row = await settings_repo.get()
    default_currency = settings_row.currency

    skipped: list[AmazonImportSkippedOrder] = []

    # Dedupe by order id (last wins), mirroring the CSV parser's by-id dict so
    # a re-scrape listing the same order twice isn't double-processed. Blank
    # ids can't be deduped meaningfully, so they're reported individually.
    deduped: dict[str, AmazonExportOrder] = {}
    for order in payload.orders:
        order_id = order.order_id.strip()
        if not order_id:
            skipped.append(AmazonImportSkippedOrder(order_id="", reason="Missing order id."))
            continue
        deduped[order_id] = order

    parsed: list[ParsedOrderInput] = []
    for order_id, order in deduped.items():
        status_value = (order.status or "").strip().lower()
        if status_value and status_value not in _ACCEPTED_STATUSES:
            skipped.append(
                AmazonImportSkippedOrder(
                    order_id=order_id,
                    reason=f"Order status not importable: {order.status}.",
                )
            )
            continue
        order_date = _normalized_iso_date(order.order_date)
        if order_date is None:
            skipped.append(
                AmazonImportSkippedOrder(
                    order_id=order_id,
                    reason="Order date is not a valid YYYY-MM-DD date.",
                )
            )
            continue
        total = _parse_decimal(order.total or "")
        if total is None or total <= 0:
            skipped.append(
                AmazonImportSkippedOrder(
                    order_id=order_id,
                    reason="Order total is missing or not a positive amount.",
                )
            )
            continue
        currency = (order.currency or "").strip().upper() or default_currency.upper()
        parsed.append(
            ParsedOrderInput(
                order_id=order_id,
                order_date=order_date,
                total=total,
                currency=currency,
                items=[
                    {
                        "title": item.title,
                        "quantity": item.quantity,
                        "price": _parse_decimal(item.price or ""),
                    }
                    for item in order.items
                ],
                shipments=[
                    ParsedShipmentInput(
                        ship_date=shipment.ship_date,
                        tracking=shipment.tracking,
                        total=_parse_decimal(shipment.total or "") or Decimal(0),
                        items=[
                            {
                                "title": item.title,
                                "quantity": item.quantity,
                                "price": _parse_decimal(item.price or ""),
                            }
                            for item in shipment.items
                        ],
                    )
                    for shipment in order.shipments
                ],
                payment_last4=order.payment_last4,
                order_url=order.order_url,
            )
        )

    result = await _ingest_orders(session, parsed, source="export")
    logger.info(
        "amazon.export scraper_version=%s domain=%s parsed=%d skipped=%d created=%d updated=%d",
        payload.scraper_version,
        payload.domain,
        len(parsed),
        len(skipped),
        result.created,
        result.updated,
    )
    return AmazonImportResponse(
        created=result.created,
        updated=result.updated,
        auto_matched=result.auto_matched,
        ambiguous=result.ambiguous,
        combined_matched=result.combined_matched,
        files=[
            AmazonImportFileReport(
                filename=payload.domain or "Amazon browser export",
                orders_parsed=len(parsed),
                skipped_rows=len(skipped),
                skipped=skipped,
            )
        ],
    )


@router.post("/match-all", response_model=AmazonMatchAllResponse)
async def match_all_amazon_orders(session: SessionDep) -> AmazonMatchAllResponse:
    repo = AmazonOrderRepository(session)
    result = await repo.auto_match_all()
    await session.commit()
    return AmazonMatchAllResponse(
        auto_matched=result.auto_matched,
        ambiguous=result.ambiguous,
        total_orders=result.total_orders,
        combined_matched=result.combined_matched,
    )


async def _expense_with_links(repo: AmazonOrderRepository, expense: Expense) -> ExpenseOut:
    linked_map = await repo.expense_linked_orders([expense.id])
    # ``resolved_note`` is intentionally left at its default (""). This hand-built
    # ExpenseOut comes from a join-table query (not the eager-loaded relationship),
    # and the /link response is discarded by the client (which re-fetches the list
    # where resolved_note IS computed). Not worth resolving here.
    return ExpenseOut(
        id=expense.id,
        name=expense.name,
        amount=expense.amount,
        date=expense.date,
        category_id=expense.category_id,
        note=expense.note,
        display_name=expense.display_name,
        importance=cast("Importance", expense.importance),
        category_source=cast("CategorySource", expense.category_source),
        amazon_order_ids=linked_map.get(expense.id, []),
    )


@router.get("/{order_id}/suggested-matches", response_model=list[ExpenseOut])
async def list_suggested_matches(order_id: str, session: SessionDep) -> list[ExpenseOut]:
    repo = AmazonOrderRepository(session)
    candidates = await repo.suggest_matches(order_id)
    linked = await repo.expense_linked_orders([c.id for c in candidates])
    # ``resolved_note`` left at default ""; this is the match-picker, which does
    # not render notes (see _expense_with_links for the same rationale).
    return [
        ExpenseOut(
            id=candidate.id,
            name=candidate.name,
            amount=candidate.amount,
            date=candidate.date,
            category_id=candidate.category_id,
            note=candidate.note,
            display_name=candidate.display_name,
            importance=cast("Importance", candidate.importance),
            category_source=cast("CategorySource", candidate.category_source),
            amazon_order_ids=linked.get(candidate.id, []),
        )
        for candidate in candidates
    ]


@router.post("/{order_id}/link", response_model=ExpenseOut)
async def link_amazon_order(
    order_id: str, payload: AmazonLinkRequest, session: SessionDep
) -> ExpenseOut:
    repo = AmazonOrderRepository(session)
    expense = await repo.link_expense(order_id, payload.expense_id)
    out = await _expense_with_links(repo, expense)
    await session.commit()
    return out


@router.post("/{order_id}/unlink", response_model=ExpenseOut)
async def unlink_amazon_order(
    order_id: str, payload: AmazonLinkRequest, session: SessionDep
) -> ExpenseOut:
    repo = AmazonOrderRepository(session)
    expense = await repo.unlink_expense(order_id, payload.expense_id)
    out = await _expense_with_links(repo, expense)
    await session.commit()
    return out


@router.patch("/{order_id}/short-name", response_model=AmazonOrderOut)
async def update_amazon_short_name(
    order_id: str, payload: AmazonShortNameRequest, session: SessionDep
) -> AmazonOrderOut:
    repo = AmazonOrderRepository(session)
    order = await repo.update_short_name(order_id, payload.short_name)
    linked = await repo.linked_expense_ids(order.id)
    out = _order_to_out(order, linked)
    await session.commit()
    return out


@router.patch("/{order_id}/category", response_model=AmazonOrderOut)
async def update_amazon_category(
    order_id: str, payload: AmazonCategoryRequest, session: SessionDep
) -> AmazonOrderOut:
    repo = AmazonOrderRepository(session)
    order = await repo.set_order_category(order_id, payload.category_id)
    linked = await repo.linked_expense_ids(order.id)
    out = _order_to_out(order, linked)
    await session.commit()
    return out


def _resolve_existing_category(name: str, categories: list[Category]) -> Category | None:
    """Find the existing category a suggested NAME would resolve to, WITHOUT
    creating one. Mirrors the id/name lookups in
    ``ExpenseRepository.resolve_or_create_category`` so the preview's
    ``suggested_category_exists`` flag matches what confirm would actually do.
    Returns ``None`` when confirming would create a new ``cat-*`` category."""
    normalized = name.strip().lower()
    if normalized in ("", "other"):
        return next((c for c in categories if c.id == "uncategorized"), None)
    candidate_id = f"cat-{slugify_category(name)}"
    canonical = titleize_slug(slugify_category(name)).lower()
    for category in categories:
        if category.id == candidate_id:
            return category
    for category in categories:
        if category.name.strip().lower() == canonical:
            return category
    return None


@router.post("/recategorize/preview", response_model=AmazonRecategorizePreviewResponse)
async def preview_recategorize_amazon_orders(
    session: SessionDep,
) -> AmazonRecategorizePreviewResponse:
    """AI-recategorise ALL eligible orders against the CURRENT AI rules and
    category set, returning a read-only preview (no writes). Rows whose
    suggestion equals the order's current category are marked ``changed=False``
    so the UI can hide them. Requires ``QUID_OPENROUTER_API_KEY``."""
    repo = AmazonOrderRepository(session)
    settings_row = await AppSettingsRepository(session).get()
    settings = get_settings()
    orders = await repo.list_all()

    category_rows = list((await session.scalars(select(Category).order_by(Category.name))).all())
    category_by_id = {category.id: category for category in category_rows}
    ai_rules = [rule.text for rule in await AiRuleRepository(session).list_all(enabled_only=True)]

    suggestions = await suggest_amazon_order_categories(
        orders,
        existing_categories=[(c.name, c.description) for c in category_rows],
        ai_rules=ai_rules,
        api_key=settings.openrouter_api_key,
        model=settings_row.categorize_model or settings.openrouter_model,
        chunk_size=settings.openrouter_chunk_size,
    )

    rows: list[AmazonRecategorizePreviewRow] = []
    changed_count = 0
    for order in orders:
        suggested_name = suggestions.get(order.id)
        if not suggested_name:
            continue
        existing = _resolve_existing_category(suggested_name, category_rows)
        current = category_by_id.get(order.category_id) if order.category_id else None
        changed = existing is None or current is None or existing.id != current.id
        if changed:
            changed_count += 1
        # For a not-yet-existing suggestion, show the canonical name confirm
        # would actually create (titleized slug), not the raw AI casing, so the
        # preview's label matches the created category.
        if existing is not None:
            suggested_label = existing.name
        else:
            suggested_label = titleize_slug(slugify_category(suggested_name)) or suggested_name
        rows.append(
            AmazonRecategorizePreviewRow(
                order_id=order.id,
                name=order.short_name or order.id,
                total=order.total,
                order_date=order.order_date,
                current_category_id=current.id if current else None,
                current_category_name=current.name if current else None,
                suggested_category_name=suggested_label,
                suggested_category_exists=existing is not None,
                changed=changed,
            )
        )
    return AmazonRecategorizePreviewResponse(
        rows=rows,
        eligible=len(rows),
        changed=changed_count,
        unchanged=len(rows) - changed_count,
    )


@router.post("/recategorize/confirm", response_model=AmazonRecategorizeConfirmResponse)
async def confirm_recategorize_amazon_orders(
    session: SessionDep, payload: AmazonRecategorizeConfirmRequest
) -> AmazonRecategorizeConfirmResponse:
    """Apply accepted AI re-categorisation rows: resolve each suggested name to
    a category (creating a ``cat-*`` when needed), overwrite the order's
    category, and propagate it onto linked overridable expenses. Unknown order
    ids are skipped. Returns counts for the run summary."""
    repo = AmazonOrderRepository(session)
    expense_repo = ExpenseRepository(session)
    created_index: dict[str, Category] = {}
    pre_existing = {category.id for category in (await session.scalars(select(Category))).all()}

    updated = 0
    expenses_updated = 0
    for row in payload.rows:
        try:
            order = await repo.get(row.order_id)
        except RepositoryError:
            continue
        category = await expense_repo.resolve_or_create_category(row.category_name, created_index)
        expenses_updated += await repo.apply_category(order.id, category.id)
        updated += 1

    post_existing = {category.id for category in (await session.scalars(select(Category))).all()}
    categories_created = len(post_existing - pre_existing)
    await session.commit()
    logger.info(
        "amazon.recategorize.confirm updated=%d categories_created=%d expenses_updated=%d",
        updated,
        categories_created,
        expenses_updated,
    )
    return AmazonRecategorizeConfirmResponse(
        updated=updated,
        categories_created=categories_created,
        expenses_updated=expenses_updated,
    )


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_amazon_order(order_id: str, session: SessionDep) -> Response:
    repo = AmazonOrderRepository(session)
    await repo.delete(order_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
