from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response, status

from quid_api.db import get_session
from quid_api.repositories.categories import CategoryRepository
from quid_api.schemas import CategoryCreate, CategoryOut, CategoryUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@router.get("", response_model=list[CategoryOut])
async def list_categories(session: SessionDep) -> list[CategoryOut]:
    repo = CategoryRepository(session)
    rows = await repo.list_all()
    return [CategoryOut.model_validate(r) for r in rows]


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(category_id: str, session: SessionDep) -> CategoryOut:
    repo = CategoryRepository(session)
    row = await repo.get(category_id)
    return CategoryOut.model_validate(row)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, session: SessionDep) -> CategoryOut:
    repo = CategoryRepository(session)
    row = await repo.create(
        name=payload.name,
        color=payload.color,
        icon=payload.icon,
        description=payload.description,
    )
    await session.commit()
    return CategoryOut.model_validate(row)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: str, payload: CategoryUpdate, session: SessionDep
) -> CategoryOut:
    repo = CategoryRepository(session)
    patch = payload.model_dump(exclude_unset=True)
    row = await repo.update(category_id, **patch)
    await session.commit()
    return CategoryOut.model_validate(row)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: str, session: SessionDep) -> Response:
    repo = CategoryRepository(session)
    await repo.delete(category_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
