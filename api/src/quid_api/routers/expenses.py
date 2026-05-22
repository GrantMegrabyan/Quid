from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from quid_api.csv_import import CsvFile, parse_csv
from quid_api.db import get_session
from quid_api.errors import RepositoryError, RepositoryErrorCode
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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


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
) -> ImportCsvResponse:
    if not files:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "At least one CSV file is required.",
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

    repo = ExpenseRepository(session)
    result = await repo.bulk_import(all_items)
    await session.commit()

    reports = []
    for parsed, (start, count) in zip(parsed_files, item_ranges, strict=True):
        decisions_slice = result.decisions[start : start + count]
        imported = sum(1 for d in decisions_slice if d)
        reports.append(
            ImportCsvFileReport(
                filename=parsed.filename,
                rows=count + parsed.skipped_rows,
                imported=imported,
                skipped_duplicates=count - imported,
                skipped_invalid_rows=parsed.skipped_rows,
            )
        )

    return ImportCsvResponse(
        imported=len(result.expenses),
        skipped_duplicates=result.skipped_duplicates,
        skipped_invalid_rows=sum(p.skipped_rows for p in parsed_files),
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
