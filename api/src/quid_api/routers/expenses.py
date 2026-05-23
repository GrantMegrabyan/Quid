from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy import select

from quid_api.ai_categorization import categorize_transactions
from quid_api.csv_import import CsvFile, parse_csv
from quid_api.db import get_session
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category
from quid_api.repositories.ai_rules import AiRuleRepository
from quid_api.repositories.expenses import BulkItem, ExpenseRepository
from quid_api.schemas import (
    BulkExpenseRequest,
    BulkExpenseResponse,
    CategoryOut,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    ImportCsvFileReport,
    ImportCsvResponse,
)
from quid_api.settings import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=0, le=10_000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ExpenseOut]:
    repo = ExpenseRepository(session)
    rows = await repo.list_all(limit=limit, offset=offset)
    return [ExpenseOut.model_validate(r) for r in rows]


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get_expense(expense_id: str, session: SessionDep) -> ExpenseOut:
    repo = ExpenseRepository(session)
    row = await repo.get(expense_id)
    return ExpenseOut.model_validate(row)


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate, session: SessionDep) -> ExpenseOut:
    repo = ExpenseRepository(session)
    row = await repo.create(
        name=payload.name,
        amount=payload.amount,
        date=payload.date,
        category_id=payload.category_id,
        note=payload.note,
    )
    await session.commit()
    return ExpenseOut.model_validate(row)


@router.post(
    "/bulk",
    response_model=BulkExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_expenses(
    payload: BulkExpenseRequest, session: SessionDep
) -> BulkExpenseResponse:
    repo = ExpenseRepository(session)
    items = [
        BulkItem(
            name=i.name,
            category=i.category,
            amount=i.amount,
            date=i.date,
            note=i.note,
        )
        for i in payload.items
    ]
    result = await repo.bulk_create(items)
    await session.commit()
    return BulkExpenseResponse(
        created=len(result.expenses),
        categories_created=[CategoryOut.model_validate(c) for c in result.categories_created],
        expenses=[ExpenseOut.model_validate(e) for e in result.expenses],
    )


@router.post(
    "/import-csv",
    response_model=ImportCsvResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_csv(
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="One or more CSV files to import.")],
    settings: SettingsDep,
    ai_categorize: Annotated[
        bool,
        Form(description="Use AI to categorise parsed transactions before saving."),
    ] = False,
) -> ImportCsvResponse:
    if not files:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "At least one CSV file is required.",
        )

    logger.info(
        "import.csv.start files=%d ai=%s",
        len(files),
        ai_categorize,
    )
    parsed_files = []
    item_ranges: list[tuple[int, int]] = []
    all_items: list[BulkItem] = []
    for upload in files:
        content = await upload.read()
        filename = upload.filename or "upload.csv"
        parsed = parse_csv(CsvFile(filename=filename, content=content))
        parsed_files.append(parsed)
        start = len(all_items)
        all_items.extend(parsed.items)
        item_ranges.append((start, len(parsed.items)))
        logger.info(
            "import.csv.parsed filename=%s parsed_rows=%d skipped_invalid=%d",
            parsed.filename,
            len(parsed.items),
            parsed.skipped_rows,
        )

    ai_categorized = 0
    if ai_categorize and all_items:
        category_names = list(await session.scalars(select(Category.name).order_by(Category.name)))
        ai_rules = [
            rule.text for rule in await AiRuleRepository(session).list_all(enabled_only=True)
        ]
        categorized = await categorize_transactions(
            all_items,
            existing_categories=category_names,
            ai_rules=ai_rules,
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
        )
        all_items = categorized.items
        ai_categorized = categorized.categorized
        ai_excluded_indices = categorized.excluded_indices
    else:
        ai_excluded_indices = frozenset()

    repo = ExpenseRepository(session)
    result = await repo.bulk_import(all_items, ai_excluded_indices=ai_excluded_indices)
    await session.commit()
    logger.info(
        "import.csv.done imported=%d duplicates=%d excluded=%d invalid=%d ai_categorized=%d",
        len(result.expenses),
        result.skipped_duplicates,
        result.skipped_excluded,
        sum(p.skipped_rows for p in parsed_files),
        ai_categorized,
    )

    reports = []
    for parsed, (start, count) in zip(parsed_files, item_ranges, strict=True):
        decisions_slice = result.decisions[start : start + count]
        imported = sum(1 for d in decisions_slice if d == "created")
        excluded = sum(1 for d in decisions_slice if d == "excluded")
        reports.append(
            ImportCsvFileReport(
                filename=parsed.filename,
                rows=count + parsed.skipped_rows,
                imported=imported,
                skipped_duplicates=sum(1 for d in decisions_slice if d == "duplicate"),
                skipped_excluded=excluded,
                skipped_invalid_rows=parsed.skipped_rows,
            )
        )

    return ImportCsvResponse(
        imported=len(result.expenses),
        skipped_duplicates=result.skipped_duplicates,
        skipped_excluded=result.skipped_excluded,
        skipped_invalid_rows=sum(p.skipped_rows for p in parsed_files),
        transactions_found=len(all_items),
        ai_categorized=ai_categorized,
        categories_created=[CategoryOut.model_validate(c) for c in result.categories_created],
        expenses=[ExpenseOut.model_validate(e) for e in result.expenses],
        files=reports,
    )


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: str, payload: ExpenseUpdate, session: SessionDep
) -> ExpenseOut:
    repo = ExpenseRepository(session)
    patch = payload.model_dump(exclude_unset=True)
    row = await repo.update(expense_id, **patch)
    await session.commit()
    return ExpenseOut.model_validate(row)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: str, session: SessionDep) -> Response:
    repo = ExpenseRepository(session)
    await repo.delete(expense_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
