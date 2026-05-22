from __future__ import annotations

from decimal import Decimal  # noqa: TC003  pydantic Field reads this at runtime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select, text

from quid_api.category_helpers import UNCATEGORIZED_COLOR, UNCATEGORIZED_ID
from quid_api.db import get_session
from quid_api.models import Category, Expense
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import ExpenseRepository
from quid_api.schemas import CategoryOut, ExpenseOut, _Camel
from quid_api.seed import seed_samples

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/testing", tags=["testing"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


async def _wipe(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM expenses"))
    await session.execute(
        text("DELETE FROM categories WHERE id != :uid"), {"uid": UNCATEGORIZED_ID}
    )
    await session.execute(
        text(
            "UPDATE categories SET name='Uncategorized', color=:c, icon='circle-help' WHERE id=:uid"
        ),
        {"c": UNCATEGORIZED_COLOR, "uid": UNCATEGORIZED_ID},
    )


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_state(
    session: SessionDep,
    with_samples: bool = False,
) -> Response:
    await _wipe(session)
    await session.commit()

    if with_samples:
        cat_repo = CategoryRepository(session)
        exp_repo = ExpenseRepository(session)
        await seed_samples(cat_repo, exp_repo)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


class _SeedCategory(_Camel):
    id: str
    name: str
    color: str
    icon: str


class _SeedExpense(_Camel):
    id: str
    name: str
    amount: Decimal
    date: str
    category_id: str
    note: str = ""


class _SeedState(_Camel):
    categories: list[_SeedCategory]
    expenses: list[_SeedExpense]


class _SeedResponse(_Camel):
    categories: list[CategoryOut]
    expenses: list[ExpenseOut]


@router.post("/seed-state", response_model=_SeedResponse, status_code=status.HTTP_201_CREATED)
async def seed_state(payload: _SeedState, session: SessionDep) -> _SeedResponse:
    await _wipe(session)
    await session.flush()

    for cat in payload.categories:
        if cat.id == UNCATEGORIZED_ID:
            await session.execute(
                text("UPDATE categories SET name=:n, color=:c, icon=:i WHERE id=:uid"),
                {"n": cat.name, "c": cat.color, "i": cat.icon, "uid": UNCATEGORIZED_ID},
            )
            continue
        session.add(Category(id=cat.id, name=cat.name, color=cat.color, icon=cat.icon))
    await session.flush()

    for exp in payload.expenses:
        session.add(
            Expense(
                id=exp.id,
                name=exp.name,
                amount=exp.amount,
                date=exp.date,
                category_id=exp.category_id,
                note=exp.note,
            )
        )
    await session.commit()

    cats = (await session.scalars(select(Category))).all()
    exps = (await session.scalars(select(Expense))).all()
    return _SeedResponse(
        categories=[CategoryOut.model_validate(c) for c in cats],
        expenses=[ExpenseOut.model_validate(e) for e in exps],
    )
