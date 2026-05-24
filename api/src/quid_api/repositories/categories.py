from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select, update

from quid_api.category_helpers import (
    UNCATEGORIZED_ID,
    color_for_category_id,
    normalize_icon,
)
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category, Expense

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _normalize_name(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _normalize_description(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


async def _find_duplicate(
    session: AsyncSession, name: str, exclude_id: str | None = None
) -> Category | None:
    nl = name.lower()
    stmt = select(Category)
    rows = (await session.scalars(stmt)).all()
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if row.name.strip().lower() == nl:
            return row
    return None


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Category]:
        result = await self.session.scalars(select(Category).order_by(Category.id))
        return list(result.all())

    async def get(self, category_id: str) -> Category:
        row = await self.session.get(Category, category_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f'Category "{category_id}" not found.',
            )
        return row

    async def create(
        self,
        name: str,
        color: str | None = None,
        icon: str | None = None,
        description: str = "",
    ) -> Category:
        clean_name = _normalize_name(name)
        if clean_name == "":
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Category name cannot be blank.",
            )

        existing = await _find_duplicate(self.session, clean_name)
        if existing is not None:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f'A category named "{clean_name}" already exists.',
            )

        new_id = f"cat-{uuid4()}"
        resolved_color = color if color else color_for_category_id(new_id)
        resolved_icon = normalize_icon(icon)

        row = Category(
            id=new_id,
            name=clean_name,
            color=resolved_color,
            icon=resolved_icon,
            description=_normalize_description(description),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(
        self,
        category_id: str,
        *,
        name: str | None = None,
        color: str | None = None,
        icon: str | None = None,
        description: str | None = None,
    ) -> Category:
        row = await self.get(category_id)

        if name is not None:
            new_name = _normalize_name(name)
            if new_name == "":
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    "Category name cannot be blank.",
                )
            if category_id == UNCATEGORIZED_ID and new_name != row.name.strip():
                raise RepositoryError(
                    RepositoryErrorCode.IMMUTABLE,
                    "The Uncategorized category name cannot be changed.",
                )
            duplicate = await _find_duplicate(self.session, new_name, exclude_id=category_id)
            if duplicate is not None:
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    f'A category named "{new_name}" already exists.',
                )
            row.name = new_name

        if color is not None:
            row.color = color

        if icon is not None:
            row.icon = normalize_icon(icon)

        if description is not None:
            row.description = _normalize_description(description)

        await self.session.flush()
        return row

    async def delete(self, category_id: str) -> None:
        if category_id == UNCATEGORIZED_ID:
            raise RepositoryError(
                RepositoryErrorCode.IMMUTABLE,
                "The Uncategorized category cannot be deleted.",
            )
        row = await self.session.get(Category, category_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f'Category "{category_id}" not found.',
            )

        await self.session.execute(
            update(Expense)
            .where(Expense.category_id == category_id)
            .values(category_id=UNCATEGORIZED_ID)
        )
        await self.session.delete(row)
        await self.session.flush()
