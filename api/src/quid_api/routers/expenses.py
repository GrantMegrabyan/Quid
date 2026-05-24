from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy import select

from quid_api.ai_categorization import categorize_transactions
from quid_api.csv_import import CsvFile, parse_csv
from quid_api.db import get_session
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category, Expense
from quid_api.refund_detection import detect_refund_pairs
from quid_api.repositories.ai_rules import AiRuleRepository
from quid_api.repositories.expenses import (
    BulkItem,
    ExpenseRepository,
    _coerce_amount,
    _normalize_text,
    _validate_amount,
    _validate_date,
    _validate_name,
)
from quid_api.repositories.import_log import ImportLogRepository
from quid_api.repositories.import_rules import ImportRuleRepository, RuleMatchItem
from quid_api.schemas import (
    BulkExpenseRequest,
    BulkExpenseResponse,
    CategoryOut,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    ImportCsvConfirmRequest,
    ImportCsvConfirmResponse,
    ImportCsvFileReport,
    ImportCsvPreviewResponse,
    ImportCsvPreviewSummary,
    ImportCsvResponse,
    ImportPreviewCategory,
    ImportPreviewKind,
    ImportPreviewRow,
)
from quid_api.settings import Settings, get_settings

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class _ParsedUpload:
    filename: str
    items: list[BulkItem]
    skipped_rows: int
    start: int


@dataclass(frozen=True)
class _PreparedImportItem:
    index: int
    filename: str
    source_row: int
    name: str
    amount: Decimal
    date: str
    note: str
    category_id: str | None
    category_name: str
    category_exists: bool
    excluded: bool = False


def _dedupe_key_hash(date: str, name: str, amount: Decimal, note: str) -> str:
    raw = f"{date}\x1f{_normalize_text(name)}\x1f{amount}\x1f{_normalize_text(note)}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def _category_maps(categories: list[Category]) -> tuple[dict[str, Category], dict[str, Category]]:
    return (
        {cat.id: cat for cat in categories},
        {_normalize_text(cat.name): cat for cat in categories},
    )


def _suggested_category(raw: str, categories: list[Category]) -> ImportPreviewCategory:
    from quid_api.category_helpers import slugify_category, titleize_slug

    category_by_id, category_by_name = _category_maps(categories)
    slug = slugify_category(raw)
    category_id = "uncategorized" if slug in ("", "other") else f"cat-{slug}"
    existing = category_by_id.get(category_id) or category_by_name.get(
        _normalize_text(titleize_slug(slug))
    )
    if existing is not None:
        return ImportPreviewCategory(id=existing.id, name=existing.name, exists=True)
    return ImportPreviewCategory(id=category_id, name=titleize_slug(slug), exists=False)


async def _read_csv_uploads(files: list[UploadFile], import_id: str) -> list[_ParsedUpload]:
    parsed_uploads: list[_ParsedUpload] = []
    next_index = 0
    for upload in files:
        content = await upload.read()
        filename = upload.filename or "upload.csv"
        parsed = parse_csv(CsvFile(filename=filename, content=content))
        parsed_uploads.append(
            _ParsedUpload(
                filename=parsed.filename,
                items=parsed.items,
                skipped_rows=parsed.skipped_rows,
                start=next_index,
            )
        )
        next_index += len(parsed.items)
        logger.info(
            "import.csv.parsed import_id=%s filename=%s parsed_rows=%d skipped_invalid=%d",
            import_id,
            parsed.filename,
            len(parsed.items),
            parsed.skipped_rows,
        )
    return parsed_uploads


async def _categorize_if_requested(
    session: AsyncSession,
    settings: Settings,
    items: list[BulkItem],
    ai_categorize: bool,
    import_id: str,
) -> tuple[list[BulkItem], int, frozenset[int]]:
    if not ai_categorize or not items:
        return items, 0, frozenset()
    category_rows = list(
        await session.execute(select(Category.name, Category.description).order_by(Category.name))
    )
    existing_categories = [(row.name, row.description) for row in category_rows]
    ai_rules = [rule.text for rule in await AiRuleRepository(session).list_all(enabled_only=True)]
    categorized = await categorize_transactions(
        items,
        existing_categories=existing_categories,
        ai_rules=ai_rules,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        chunk_size=settings.openrouter_chunk_size,
    )
    logger.info(
        "import.csv.ai.done import_id=%s categorized=%d excluded=%d model=%s",
        import_id,
        categorized.categorized,
        len(categorized.excluded_indices),
        settings.openrouter_model,
    )
    return categorized.items, categorized.categorized, categorized.excluded_indices


async def _prepare_preview_items(
    session: AsyncSession,
    parsed_uploads: list[_ParsedUpload],
    items: list[BulkItem],
    ai_excluded_indices: frozenset[int],
) -> list[_PreparedImportItem]:
    categories = list((await session.scalars(select(Category))).all())
    rule_repo = ImportRuleRepository(session)
    prepared: list[_PreparedImportItem] = []
    source_by_index: dict[int, tuple[str, int]] = {}
    for upload in parsed_uploads:
        for offset in range(len(upload.items)):
            source_by_index[upload.start + offset] = (upload.filename, offset + 2)

    for idx, item in enumerate(items):
        filename, source_row = source_by_index[idx]
        try:
            clean_name = _validate_name(item.name)
            clean_amount = _validate_amount(abs(_coerce_amount(item.amount)))
            clean_date = _validate_date(item.date)
        except RepositoryError as exc:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION, f"row {idx}: {exc.message}"
            ) from exc
        if idx in ai_excluded_indices:
            suggested = _suggested_category(item.category, categories)
            prepared.append(
                _PreparedImportItem(
                    index=idx,
                    filename=filename,
                    source_row=source_row,
                    name=clean_name,
                    amount=clean_amount,
                    date=clean_date,
                    note=item.note or "",
                    category_id=suggested.id,
                    category_name=suggested.name,
                    category_exists=suggested.exists,
                    excluded=True,
                )
            )
            continue
        rule = await rule_repo.first_match(
            RuleMatchItem(name=clean_name, amount=clean_amount, date=clean_date)
        )
        if rule is not None and rule.action == "exclude":
            suggested = _suggested_category(item.category, categories)
            prepared.append(
                _PreparedImportItem(
                    index=idx,
                    filename=filename,
                    source_row=source_row,
                    name=clean_name,
                    amount=clean_amount,
                    date=clean_date,
                    note=item.note or "",
                    category_id=suggested.id,
                    category_name=suggested.name,
                    category_exists=suggested.exists,
                    excluded=True,
                )
            )
            continue
        if rule is not None and rule.action == "categorize":
            assert rule.target_category_id is not None
            category = await session.get(Category, rule.target_category_id)
            assert category is not None
            category_id: str | None = category.id
            category_name = category.name
            category_exists = True
        else:
            suggested = _suggested_category(item.category, categories)
            category_id = suggested.id
            category_name = suggested.name
            category_exists = suggested.exists
        prepared.append(
            _PreparedImportItem(
                index=idx,
                filename=filename,
                source_row=source_row,
                name=clean_name,
                amount=clean_amount,
                date=clean_date,
                note=item.note or "",
                category_id=category_id,
                category_name=category_name,
                category_exists=category_exists,
            )
        )
    return prepared


async def _build_preview_rows(
    session: AsyncSession, prepared: list[_PreparedImportItem]
) -> list[ImportPreviewRow]:
    categories = list((await session.scalars(select(Category))).all())
    category_by_id, _ = _category_maps(categories)
    active_by_key: dict[tuple[str, str, Decimal, str], list[_PreparedImportItem]] = defaultdict(
        list
    )
    rows: list[ImportPreviewRow] = []
    for item in prepared:
        suggested = ImportPreviewCategory(
            id=item.category_id,
            name=item.category_name,
            exists=item.category_exists,
        )
        key_hash = _dedupe_key_hash(item.date, item.name, item.amount, item.note)
        if item.excluded:
            rows.append(
                ImportPreviewRow(
                    preview_row_id=f"row-{item.index}",
                    filename=item.filename,
                    source_row=item.source_row,
                    dedupe_key_hash=key_hash,
                    name=item.name,
                    amount=item.amount,
                    date=item.date,
                    note=item.note,
                    kind="excluded",
                    suggested_category=suggested,
                )
            )
            continue
        key = (item.date, _normalize_text(item.name), item.amount, _normalize_text(item.note))
        active_by_key[key].append(item)

    for key, key_items in active_by_key.items():
        date, name_norm, amount, note_norm = key
        existing_candidates = list(
            (
                await session.scalars(
                    select(Expense)
                    .where(Expense.date == date, Expense.amount == amount)
                    .order_by(Expense.id)
                )
            ).all()
        )
        existing = [
            expense
            for expense in existing_candidates
            if _normalize_text(expense.name) == name_norm
            and _normalize_text(expense.note) == note_norm
        ]
        for occurrence, item in enumerate(key_items):
            suggested = ImportPreviewCategory(
                id=item.category_id,
                name=item.category_name,
                exists=item.category_exists,
            )
            key_hash = _dedupe_key_hash(item.date, item.name, item.amount, item.note)
            if occurrence >= len(existing):
                kind: ImportPreviewKind = "create"
                existing_expense_id = None
                existing_category_id = None
                existing_category_name = None
            else:
                matched = existing[occurrence]
                existing_expense_id = matched.id
                existing_category_id = matched.category_id
                matched_category = category_by_id.get(matched.category_id)
                existing_category_name = (
                    matched_category.name if matched_category is not None else matched.category_id
                )
                kind = (
                    "duplicate_same_category"
                    if matched.category_id == item.category_id
                    else "category_update"
                )
            rows.append(
                ImportPreviewRow(
                    preview_row_id=f"row-{item.index}",
                    filename=item.filename,
                    source_row=item.source_row,
                    dedupe_key_hash=key_hash,
                    name=item.name,
                    amount=item.amount,
                    date=item.date,
                    note=item.note,
                    kind=kind,
                    existing_expense_id=existing_expense_id,
                    existing_category_id=existing_category_id,
                    existing_category_name=existing_category_name,
                    suggested_category=suggested,
                )
            )
    return sorted(rows, key=lambda row: (row.filename, row.source_row, row.preview_row_id))


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
    "/import-csv/preview",
    response_model=ImportCsvPreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_import_csv(
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="One or more CSV files to preview.")],
    settings: SettingsDep,
    ai_categorize: Annotated[
        bool,
        Form(description="Use AI to categorise parsed transactions before previewing."),
    ] = True,
) -> ImportCsvPreviewResponse:
    if not files:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "At least one CSV file is required.",
        )

    import_id = str(uuid4())
    logger.info(
        "import.preview.start import_id=%s files=%d ai=%s", import_id, len(files), ai_categorize
    )
    parsed_uploads = await _read_csv_uploads(files, import_id)
    all_items = [item for upload in parsed_uploads for item in upload.items]
    all_items, ai_categorized, ai_excluded_indices = await _categorize_if_requested(
        session,
        settings,
        all_items,
        ai_categorize,
        import_id,
    )
    refund_indices = (
        detect_refund_pairs(all_items, window_days=settings.refund_window_days)
        - ai_excluded_indices
    )
    logger.info(
        "import.preview.refunds import_id=%s refunds=%d",
        import_id,
        len(refund_indices),
    )
    excluded_indices = ai_excluded_indices | refund_indices
    prepared = await _prepare_preview_items(session, parsed_uploads, all_items, excluded_indices)
    rows = await _build_preview_rows(session, prepared)
    summary = ImportCsvPreviewSummary(
        creates=sum(1 for row in rows if row.kind == "create"),
        category_updates=sum(1 for row in rows if row.kind == "category_update"),
        hidden_duplicates=sum(1 for row in rows if row.kind == "duplicate_same_category"),
        excluded=sum(1 for row in rows if row.kind == "excluded"),
        invalid_rows=sum(upload.skipped_rows for upload in parsed_uploads),
        ai_categorized=ai_categorized,
        skipped_refunds=len(refund_indices),
    )
    logger.info(
        "import.preview.plan import_id=%s creates=%d category_updates=%d hidden_duplicates=%d "
        "excluded=%d invalid=%d ai_categorized=%d refunds=%d",
        import_id,
        summary.creates,
        summary.category_updates,
        summary.hidden_duplicates,
        summary.excluded,
        summary.invalid_rows,
        summary.ai_categorized,
        summary.skipped_refunds,
    )
    reports = []
    for upload in parsed_uploads:
        file_rows = [row for row in rows if row.filename == upload.filename]
        reports.append(
            ImportCsvFileReport(
                filename=upload.filename,
                rows=len(upload.items) + upload.skipped_rows,
                imported=sum(1 for row in file_rows if row.kind == "create"),
                skipped_duplicates=sum(
                    1 for row in file_rows if row.kind == "duplicate_same_category"
                ),
                skipped_excluded=sum(1 for row in file_rows if row.kind == "excluded"),
                skipped_invalid_rows=upload.skipped_rows,
            )
        )
    visible_rows = [row for row in rows if row.kind != "duplicate_same_category"]
    return ImportCsvPreviewResponse(
        import_id=import_id,
        rows=visible_rows,
        summary=summary,
        files=reports,
    )


@router.post(
    "/import-csv/confirm",
    response_model=ImportCsvConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_import_csv(
    payload: ImportCsvConfirmRequest, session: SessionDep
) -> ImportCsvConfirmResponse:
    logger.info(
        "import.confirm.start import_id=%s creates=%d updates=%d",
        payload.import_id,
        len(payload.creates),
        len(payload.category_updates),
    )
    repo = ExpenseRepository(session)
    items = [
        BulkItem(
            name=row.name,
            category=row.category_name,
            amount=row.amount,
            date=row.date,
            note=row.note,
        )
        for row in payload.creates
    ]
    import_result = await repo.bulk_import(items) if items else None

    created_categories = list(import_result.categories_created) if import_result else []
    created_expenses = list(import_result.expenses) if import_result else []
    skipped_duplicates = import_result.skipped_duplicates if import_result else 0
    created_category_index = {category.id: category for category in created_categories}
    updated = 0
    stale_updates = 0
    kept_existing = 0
    for row in payload.category_updates:
        if not row.accept:
            kept_existing += 1
            continue
        expense = await session.get(Expense, row.existing_expense_id)
        if expense is None:
            stale_updates += 1
            continue
        current_hash = _dedupe_key_hash(expense.date, expense.name, expense.amount, expense.note)
        if current_hash != row.dedupe_key_hash:
            stale_updates += 1
            continue
        old_category = expense.category_id
        category = await repo._resolve_or_create_category(row.category_name, created_category_index)
        if category.id != old_category:
            expense.category_id = category.id
            updated += 1
            logger.info(
                "import.confirm.update_category import_id=%s expense=%s old=%s new=%s row=%s",
                payload.import_id,
                expense.id,
                old_category,
                category.id,
                row.preview_row_id,
            )
        else:
            kept_existing += 1

    log_repo = ImportLogRepository(session)
    await log_repo.create(
        files=[],
        imported=len(created_expenses),
        updated=updated,
        skipped_duplicates=skipped_duplicates,
        skipped_excluded=0,
        skipped_invalid_rows=0,
    )
    await session.commit()
    logger.info(
        "import.confirm.done import_id=%s created=%d updated=%d duplicates=%d stale_updates=%d "
        "kept_existing=%d categories_created=%d",
        payload.import_id,
        len(created_expenses),
        updated,
        skipped_duplicates,
        stale_updates,
        kept_existing,
        len(created_category_index),
    )
    return ImportCsvConfirmResponse(
        created=len(created_expenses),
        updated=updated,
        skipped_duplicates=skipped_duplicates,
        skipped_stale_updates=stale_updates,
        kept_existing=kept_existing,
        categories_created=[CategoryOut.model_validate(c) for c in created_category_index.values()],
        expenses=[ExpenseOut.model_validate(e) for e in created_expenses],
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

    import_id = str(uuid4())
    logger.info(
        "import.csv.start import_id=%s files=%d ai=%s",
        import_id,
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
            "import.csv.parsed import_id=%s filename=%s parsed_rows=%d skipped_invalid=%d",
            import_id,
            parsed.filename,
            len(parsed.items),
            parsed.skipped_rows,
        )

    ai_categorized = 0
    if ai_categorize and all_items:
        category_rows = list(
            await session.execute(
                select(Category.name, Category.description).order_by(Category.name)
            )
        )
        existing_categories = [(row.name, row.description) for row in category_rows]
        ai_rules = [
            rule.text for rule in await AiRuleRepository(session).list_all(enabled_only=True)
        ]
        categorized = await categorize_transactions(
            all_items,
            existing_categories=existing_categories,
            ai_rules=ai_rules,
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            chunk_size=settings.openrouter_chunk_size,
        )
        all_items = categorized.items
        ai_categorized = categorized.categorized
        ai_excluded_indices = categorized.excluded_indices
        logger.info(
            "import.csv.ai.done import_id=%s categorized=%d excluded=%d model=%s",
            import_id,
            ai_categorized,
            len(ai_excluded_indices),
            settings.openrouter_model,
        )
    else:
        ai_excluded_indices = frozenset()

    refund_indices = (
        detect_refund_pairs(all_items, window_days=settings.refund_window_days)
        - ai_excluded_indices
    )
    logger.info(
        "import.csv.refunds import_id=%s refunds=%d",
        import_id,
        len(refund_indices),
    )
    excluded_indices = ai_excluded_indices | refund_indices

    repo = ExpenseRepository(session)
    result = await repo.bulk_import(all_items, ai_excluded_indices=excluded_indices)
    log_repo = ImportLogRepository(session)
    await log_repo.create(
        files=[p.filename for p in parsed_files],
        imported=len(result.expenses),
        updated=0,
        skipped_duplicates=result.skipped_duplicates,
        skipped_excluded=result.skipped_excluded,
        skipped_invalid_rows=sum(p.skipped_rows for p in parsed_files),
    )
    await session.commit()
    logger.info(
        "import.csv.done import_id=%s imported=%d duplicates=%d excluded=%d refunds=%d "
        "invalid=%d ai_categorized=%d",
        import_id,
        len(result.expenses),
        result.skipped_duplicates,
        result.skipped_excluded,
        len(refund_indices),
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
        skipped_refunds=len(refund_indices),
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
