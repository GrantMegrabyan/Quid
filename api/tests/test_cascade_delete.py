from __future__ import annotations

from sqlalchemy import select

from quid_api.category_helpers import UNCATEGORIZED_ID
from quid_api.models import Expense
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import ExpenseRepository


async def test_delete_category_reparents_expenses_to_uncategorized(session):
    cat_repo = CategoryRepository(session)
    exp_repo = ExpenseRepository(session)

    target = await cat_repo.create(name="Travel")
    other = await cat_repo.create(name="Bills")

    moved_a = await exp_repo.create(
        name="Hotel", amount="120", date="2026-05-01", category_id=target.id
    )
    moved_b = await exp_repo.create(
        name="Flight", amount="240", date="2026-05-02", category_id=target.id
    )
    stay_put = await exp_repo.create(
        name="Phone", amount="30", date="2026-05-03", category_id=other.id
    )
    moved_a_id = moved_a.id
    moved_b_id = moved_b.id
    stay_put_id = stay_put.id
    other_id = other.id

    reassigned = await cat_repo.delete(target.id)
    await session.commit()
    assert reassigned == 2

    expenses = (await session.scalars(select(Expense))).all()
    by_id = {e.id: e.category_id for e in expenses}
    assert by_id[moved_a_id] == UNCATEGORIZED_ID
    assert by_id[moved_b_id] == UNCATEGORIZED_ID
    assert by_id[stay_put_id] == other_id


async def test_delete_category_with_no_expenses_succeeds(session):
    cat_repo = CategoryRepository(session)
    cat = await cat_repo.create(name="Empty")
    reassigned = await cat_repo.delete(cat.id)
    assert reassigned == 0

    rows = await cat_repo.list_all()
    assert cat.id not in [c.id for c in rows]


async def test_sqlite_foreign_keys_enabled(engine, session):
    cat_repo = CategoryRepository(session)
    exp_repo = ExpenseRepository(session)

    cat = await cat_repo.create(name="X")
    exp = await exp_repo.create(name="row", amount="1", date="2026-05-01", category_id=cat.id)
    assert exp.category_id == cat.id
