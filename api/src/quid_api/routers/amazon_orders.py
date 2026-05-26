from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from quid_api.amazon_csv_import import AmazonCsvFile, parse_amazon_csv
from quid_api.db import get_session
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.amazon_orders import (
    AmazonOrderRepository,
    ParsedOrderInput,
    deserialize_items,
)
from quid_api.repositories.app_settings import AppSettingsRepository
from quid_api.schemas import (
    AmazonImportFileReport,
    AmazonImportResponse,
    AmazonLinkRequest,
    AmazonMatchAllResponse,
    AmazonOrderItem,
    AmazonOrderOut,
    ExpenseOut,
    Importance,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import AmazonOrder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/amazon-orders", tags=["amazon-orders"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


def _order_to_out(order: AmazonOrder, linked_expense_ids: list[str]) -> AmazonOrderOut:
    items_data = deserialize_items(order.items_json)
    items = [
        AmazonOrderItem(
            title=cast("str", item["title"]),
            quantity=cast("int", item["quantity"]),
            price=item["price"],  # type: ignore[arg-type]
        )
        for item in items_data
    ]
    return AmazonOrderOut(
        id=order.id,
        order_date=order.order_date,
        total=order.total,
        currency=order.currency,
        items=items,
        payment_last4=order.payment_last4,
        order_url=order.order_url,
        imported_at=order.imported_at,
        linked_expense_ids=linked_expense_ids,
    )


@router.get("", response_model=list[AmazonOrderOut])
async def list_amazon_orders(session: SessionDep) -> list[AmazonOrderOut]:
    repo = AmazonOrderRepository(session)
    orders = await repo.list_all()
    links = await repo.linked_map([order.id for order in orders])
    return [_order_to_out(order, links.get(order.id, [])) for order in orders]


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

    repo = AmazonOrderRepository(session)
    reports: list[AmazonImportFileReport] = []
    total_created = 0
    total_updated = 0
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
                payment_last4=order.payment_last4,
                order_url=order.order_url,
            )
            for order in parsed.orders
        ]
        result = await repo.bulk_upsert(payloads)
        total_created += result.created
        total_updated += result.updated
        reports.append(
            AmazonImportFileReport(
                filename=filename,
                orders_parsed=len(parsed.orders),
                skipped_rows=parsed.skipped_rows,
            )
        )
        logger.info(
            "amazon.import filename=%s parsed=%d created=%d updated=%d skipped_rows=%d",
            filename,
            len(parsed.orders),
            result.created,
            result.updated,
            parsed.skipped_rows,
        )

    match_result = await repo.auto_match_all()
    await session.commit()
    return AmazonImportResponse(
        created=total_created,
        updated=total_updated,
        auto_matched=match_result.auto_matched,
        ambiguous=match_result.ambiguous,
        files=reports,
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
    )


@router.get("/{order_id}/suggested-matches", response_model=list[ExpenseOut])
async def list_suggested_matches(order_id: str, session: SessionDep) -> list[ExpenseOut]:
    repo = AmazonOrderRepository(session)
    candidates = await repo.suggest_matches(order_id)
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
            amazon_order_id=candidate.amazon_order_id,
        )
        for candidate in candidates
    ]


@router.post("/{order_id}/link", response_model=ExpenseOut)
async def link_amazon_order(
    order_id: str, payload: AmazonLinkRequest, session: SessionDep
) -> ExpenseOut:
    repo = AmazonOrderRepository(session)
    expense = await repo.link_expense(order_id, payload.expense_id)
    await session.commit()
    return ExpenseOut.model_validate(expense)


@router.post("/{order_id}/unlink", response_model=ExpenseOut)
async def unlink_amazon_order(
    order_id: str, payload: AmazonLinkRequest, session: SessionDep
) -> ExpenseOut:
    repo = AmazonOrderRepository(session)
    expense = await repo.unlink_expense(order_id, payload.expense_id)
    await session.commit()
    return ExpenseOut.model_validate(expense)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_amazon_order(order_id: str, session: SessionDep) -> Response:
    repo = AmazonOrderRepository(session)
    await repo.delete(order_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
