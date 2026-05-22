from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text

from quid_api.category_helpers import UNCATEGORIZED_COLOR, UNCATEGORIZED_ID
from quid_api.db import get_session
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import ExpenseRepository
from quid_api.seed import seed_samples

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/testing", tags=["testing"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_state(
    session: SessionDep,
    with_samples: bool = False,
) -> Response:
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
    await session.commit()

    if with_samples:
        cat_repo = CategoryRepository(session)
        exp_repo = ExpenseRepository(session)
        await seed_samples(cat_repo, exp_repo)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
