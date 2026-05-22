from __future__ import annotations

import re
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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
