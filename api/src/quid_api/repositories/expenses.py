from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from quid_api.category_helpers import (
    UNCATEGORIZED_ID,
    color_for_category_id,
    normalize_icon,
    slugify_category,
    titleize_slug,
)
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category, Expense
from quid_api.repositories.import_rules import ImportRuleRepository, RuleMatchItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WS_RE = re.compile(r"\s+")


def _normalize_text(value: str) -> str:
    """Normalise free-text fields for dedup comparison.

    Lower-cases, strips outer whitespace, collapses internal runs of
    whitespace. Mirrors the SQL ``lower(trim(...))`` we issue against the DB
    so the in-file Counter and the existing-row query stay in lockstep.
    """
    return _WS_RE.sub(" ", (value or "").strip().lower())


def _coerce_amount(raw: object) -> Decimal:
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        return Decimal(str(raw))
    if isinstance(raw, str):
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"Amount is not a valid number: {raw!r}",
            ) from exc
    raise RepositoryError(
        RepositoryErrorCode.VALIDATION,
        f"Amount must be a number, got {type(raw).__name__}",
    )


def _validate_amount(amount: Decimal) -> Decimal:
    if amount <= 0:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Amount must be positive.",
        )
    quantized = amount.quantize(Decimal("0.01"))
    if quantized != amount:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Amount must have at most 2 decimal places.",
        )
    return quantized


def _validate_date(date: str) -> str:
    if not _DATE_RE.match(date):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            f"Date must be YYYY-MM-DD, got {date!r}",
        )
    return date


def _validate_name(name: str) -> str:
    cleaned = name.strip() if name is not None else ""
    if cleaned == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Expense name cannot be blank.",
        )
    return cleaned


@dataclass(frozen=True)
class BulkItem:
    name: str
    category: str
    amount: Decimal
    date: str
    note: str = ""


@dataclass(frozen=True)
class BulkResult:
    expenses: list[Expense]
    categories_created: list[Category]


@dataclass(frozen=True)
class ImportResult:
    expenses: list[Expense]
    categories_created: list[Category]
    skipped_duplicates: int
    skipped_excluded: int
    decisions: list[str]


class ExpenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, *, limit: int | None = None, offset: int = 0) -> list[Expense]:
        if offset < 0:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Offset must be >= 0.",
            )
        if limit is not None and limit < 0:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Limit must be >= 0.",
            )
        stmt = select(Expense).order_by(Expense.date.desc(), Expense.id.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get(self, expense_id: str) -> Expense:
        row = await self.session.get(Expense, expense_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Expense not found: {expense_id}",
            )
        return row

    async def _ensure_category_exists(self, category_id: str) -> None:
        existing = await self.session.get(Category, category_id)
        if existing is None:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f'Category "{category_id}" does not exist.',
            )

    async def create(
        self,
        *,
        name: str,
        amount: object,
        date: str,
        category_id: str,
        note: str = "",
    ) -> Expense:
        clean_name = _validate_name(name)
        clean_amount = _validate_amount(_coerce_amount(amount))
        clean_date = _validate_date(date)
        await self._ensure_category_exists(category_id)

        row = Expense(
            id=str(uuid4()),
            name=clean_name,
            amount=clean_amount,
            date=clean_date,
            category_id=category_id,
            note=note or "",
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(
        self,
        expense_id: str,
        *,
        name: str | None = None,
        amount: object | None = None,
        date: str | None = None,
        category_id: str | None = None,
        note: str | None = None,
    ) -> Expense:
        row = await self.get(expense_id)

        if name is not None:
            row.name = _validate_name(name)
        if amount is not None:
            row.amount = _validate_amount(_coerce_amount(amount))
        if date is not None:
            row.date = _validate_date(date)
        if category_id is not None:
            await self._ensure_category_exists(category_id)
            row.category_id = category_id
        if note is not None:
            row.note = note

        await self.session.flush()
        return row

    async def delete(self, expense_id: str) -> None:
        row = await self.session.get(Expense, expense_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Expense not found: {expense_id}",
            )
        await self.session.delete(row)
        await self.session.flush()

    async def _resolve_or_create_category(
        self, raw_category: str, created_index: dict[str, Category]
    ) -> Category:
        normalized = raw_category.strip().lower()
        if normalized == "" or normalized == "other":
            uncat = await self.session.get(Category, UNCATEGORIZED_ID)
            assert uncat is not None
            return uncat

        slug = slugify_category(raw_category)
        candidate_id = f"cat-{slug}"
        canonical_name = titleize_slug(slug)

        if candidate_id in created_index:
            return created_index[candidate_id]

        existing_by_id = await self.session.get(Category, candidate_id)
        if existing_by_id is not None:
            return existing_by_id

        nl = canonical_name.lower()
        all_existing = (await self.session.scalars(select(Category))).all()
        for cat in all_existing:
            if cat.name.strip().lower() == nl:
                return cat

        new_cat = Category(
            id=candidate_id,
            name=canonical_name,
            color=color_for_category_id(candidate_id),
            icon=normalize_icon(None),
        )
        self.session.add(new_cat)
        await self.session.flush()
        created_index[candidate_id] = new_cat
        return new_cat

    async def bulk_create(self, items: list[BulkItem]) -> BulkResult:
        if not items:
            return BulkResult(expenses=[], categories_created=[])

        created_categories: dict[str, Category] = {}
        created_expenses: list[Expense] = []

        for idx, item in enumerate(items):
            try:
                clean_name = _validate_name(item.name)
                coerced_amount = _coerce_amount(item.amount)
                magnitude = abs(coerced_amount)
                clean_amount = _validate_amount(magnitude)
                clean_date = _validate_date(item.date)
            except RepositoryError as exc:
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    f"row {idx}: {exc.message}",
                ) from exc

            category = await self._resolve_or_create_category(item.category, created_categories)

            expense = Expense(
                id=str(uuid4()),
                name=clean_name,
                amount=clean_amount,
                date=clean_date,
                category_id=category.id,
                note=item.note or "",
            )
            self.session.add(expense)
            created_expenses.append(expense)

        await self.session.flush()
        return BulkResult(
            expenses=created_expenses,
            categories_created=list(created_categories.values()),
        )

    async def bulk_import(
        self, items: list[BulkItem], *, ai_excluded_indices: frozenset[int] = frozenset()
    ) -> ImportResult:
        """Idempotent bulk insert.

        Dedup key: ``(date, lower(trim(name)), amount, lower(trim(note)))``.

        Category is intentionally NOT part of the key. AI categorisation is
        non-deterministic across runs, import-rule sets change over time, and
        users re-categorise rows by hand. Including category in the key let
        identical transactions slip through as duplicates whenever the
        category drifted between imports. Same merchant, same day, same
        amount, same note is the same transaction regardless of category.

        For each unique normalised key we insert
        ``max(0, in_file_count - existing_in_db)`` rows, so re-uploading the
        same CSV is a no-op while several legitimate identical transactions
        in the SAME file still accumulate.
        """
        if not items:
            logger.info("import.bulk.empty")
            return ImportResult(
                expenses=[],
                categories_created=[],
                skipped_duplicates=0,
                skipped_excluded=0,
                decisions=[],
            )

        logger.info("import.bulk.start items=%d", len(items))
        created_categories: dict[str, Category] = {}
        rule_repo = ImportRuleRepository(self.session)
        prepared: list[tuple[int, Category, Decimal, str, str, str]] = []
        decisions = ["pending" for _ in items]
        rule_excluded = 0
        rule_categorised = 0
        for idx, item in enumerate(items):
            if idx in ai_excluded_indices:
                decisions[idx] = "excluded"
                rule_excluded += 1
                logger.debug("import.bulk.ai_excluded row=%d name=%r", idx, item.name)
                continue
            try:
                clean_name = _validate_name(item.name)
                clean_amount = _validate_amount(abs(_coerce_amount(item.amount)))
                clean_date = _validate_date(item.date)
            except RepositoryError as exc:
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    f"row {idx}: {exc.message}",
                ) from exc
            rule = await rule_repo.first_match(
                RuleMatchItem(name=clean_name, amount=clean_amount, date=clean_date)
            )
            if rule is not None and rule.action == "exclude":
                decisions[idx] = "excluded"
                rule_excluded += 1
                logger.debug(
                    "import.bulk.rule_excluded row=%d name=%r rule=%s",
                    idx,
                    clean_name,
                    rule.id,
                )
                continue
            if rule is not None and rule.action == "categorize":
                assert rule.target_category_id is not None
                category = await self.session.get(Category, rule.target_category_id)
                assert category is not None
                rule_categorised += 1
                logger.debug(
                    "import.bulk.rule_categorised row=%d name=%r rule=%s category=%s",
                    idx,
                    clean_name,
                    rule.id,
                    category.id,
                )
            else:
                category = await self._resolve_or_create_category(item.category, created_categories)
            prepared.append((idx, category, clean_amount, clean_date, clean_name, item.note or ""))

        DedupKey = tuple[str, str, Decimal, str]
        in_file_counts: Counter[DedupKey] = Counter()
        for _, _cat, amount, date, name, note in prepared:
            in_file_counts[(date, _normalize_text(name), amount, _normalize_text(note))] += 1

        quotas: dict[DedupKey, int] = {}
        for key, in_file in in_file_counts.items():
            date, name_norm, amount, note_norm = key
            existing_candidates = list(
                (
                    await self.session.scalars(
                        select(Expense)
                        .where(Expense.date == date, Expense.amount == amount)
                        .order_by(Expense.id)
                    )
                ).all()
            )
            existing = sum(
                1
                for expense in existing_candidates
                if _normalize_text(expense.name) == name_norm
                and _normalize_text(expense.note) == note_norm
            )
            quotas[key] = max(0, in_file - existing)
            logger.debug(
                "import.bulk.dedup date=%s name=%r amount=%s in_file=%d candidates=%d "
                "existing=%d quota=%d",
                date,
                name_norm,
                amount,
                in_file,
                len(existing_candidates),
                existing,
                quotas[key],
            )

        created_expenses: list[Expense] = []
        skipped = 0
        for item_idx, cat, amount, date, name, note in prepared:
            key = (date, _normalize_text(name), amount, _normalize_text(note))
            if quotas[key] > 0:
                quotas[key] -= 1
                row = Expense(
                    id=str(uuid4()),
                    name=name,
                    amount=amount,
                    date=date,
                    category_id=cat.id,
                    note=note,
                )
                self.session.add(row)
                created_expenses.append(row)
                decisions[item_idx] = "created"
            else:
                skipped += 1
                decisions[item_idx] = "duplicate"

        await self.session.flush()
        logger.info(
            "import.bulk.done created=%d duplicates=%d excluded=%d rule_categorised=%d "
            "categories_created=%d",
            len(created_expenses),
            skipped,
            rule_excluded,
            rule_categorised,
            len(created_categories),
        )
        return ImportResult(
            expenses=created_expenses,
            categories_created=list(created_categories.values()),
            skipped_duplicates=skipped,
            skipped_excluded=sum(1 for d in decisions if d == "excluded"),
            decisions=decisions,
        )
