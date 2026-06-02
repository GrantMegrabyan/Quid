from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.categories import CategoryRepository
from quid_api.repositories.expenses import ExpenseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from quid_api.models import Category

UUID4_STRING_LENGTH = 36


async def _make_category(session: AsyncSession, name: str = "Groceries") -> Category:
    repo = CategoryRepository(session)
    return await repo.create(name=name)


async def test_list_empty(session):
    repo = ExpenseRepository(session)
    rows = await repo.list_all()
    assert rows == []


async def test_create_assigns_uuid_and_persists(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(
        name="Whole Foods",
        amount="58.24",
        date="2026-05-22",
        category_id=cat.id,
        note="weekly",
    )
    assert len(exp.id) == UUID4_STRING_LENGTH
    assert exp.amount == Decimal("58.24")
    assert exp.note == "weekly"


async def test_create_amount_must_be_positive(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="x", amount="0", date="2026-05-22", category_id=cat.id)
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_create_amount_max_two_decimals(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="x", amount="10.001", date="2026-05-22", category_id=cat.id)
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_create_amount_accepts_float_and_decimal(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    a = await repo.create(name="a", amount=10.50, date="2026-05-22", category_id=cat.id)
    b = await repo.create(name="b", amount=Decimal("12.34"), date="2026-05-22", category_id=cat.id)
    assert a.amount == Decimal("10.50")
    assert b.amount == Decimal("12.34")


async def test_create_rejects_bad_date(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="x", amount="1", date="22/05/2026", category_id=cat.id)
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_create_rejects_blank_name(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="  ", amount="1", date="2026-05-22", category_id=cat.id)
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_create_rejects_missing_category(session):
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="x", amount="1", date="2026-05-22", category_id="cat-nope")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_list_sorted_by_date_desc(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    await repo.create(name="a", amount="1", date="2026-01-01", category_id=cat.id)
    await repo.create(name="b", amount="1", date="2026-03-01", category_id=cat.id)
    await repo.create(name="c", amount="1", date="2026-02-01", category_id=cat.id)
    rows = await repo.list_all()
    assert [r.date for r in rows] == ["2026-03-01", "2026-02-01", "2026-01-01"]


async def test_list_pagination(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    for d in ["2026-01-01", "2026-02-01", "2026-03-01"]:
        await repo.create(name=d, amount="1", date=d, category_id=cat.id)
    rows = await repo.list_all(limit=1, offset=1)
    assert len(rows) == 1
    assert rows[0].date == "2026-02-01"


async def test_list_rejects_negative_offset(session):
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError):
        await repo.list_all(offset=-1)


async def test_list_date_range_half_open_filter(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    await repo.create(name="before", amount="1", date="2026-05-31", category_id=cat.id)
    await repo.create(name="start", amount="1", date="2026-06-01", category_id=cat.id)
    await repo.create(name="mid", amount="1", date="2026-06-15", category_id=cat.id)
    await repo.create(name="end", amount="1", date="2026-06-30", category_id=cat.id)
    await repo.create(name="after", amount="1", date="2026-07-01", category_id=cat.id)

    rows = await repo.list_all(date_from="2026-06-01", date_to="2026-06-30")
    names = sorted(r.name for r in rows)
    assert names == ["end", "mid", "start"]


async def test_list_date_range_includes_timestamped_boundary_rows(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    # A late-in-the-day timestamped row on the inclusive upper bound must be
    # included (the upper bound is exclusive at the FOLLOWING day), and a
    # date-only row on the lower bound must be included.
    await repo.create(name="lower", amount="1", date="2026-06-01", category_id=cat.id)
    await repo.create(name="upper-ts", amount="1", date="2026-06-30T23:59:59", category_id=cat.id)
    await repo.create(
        name="next-day-ts", amount="1", date="2026-07-01T00:00:00", category_id=cat.id
    )

    rows = await repo.list_all(date_from="2026-06-01", date_to="2026-06-30")
    names = sorted(r.name for r in rows)
    assert names == ["lower", "upper-ts"]


async def test_list_date_range_rejects_bad_date(session):
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.list_all(date_from="2026-13-40")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_get_missing(session):
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.get("missing")
    assert exc.value.code == RepositoryErrorCode.NOT_FOUND


async def test_update_partial(session):
    cat = await _make_category(session)
    other = await _make_category(session, name="Other")
    repo = ExpenseRepository(session)
    exp = await repo.create(name="A", amount="10", date="2026-01-01", category_id=cat.id, note="hi")
    updated = await repo.update(exp.id, name="B", category_id=other.id)
    assert updated.name == "B"
    assert updated.category_id == other.id
    assert updated.amount == Decimal("10")
    assert updated.date == "2026-01-01"
    assert updated.note == "hi"


async def test_update_missing(session):
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.update("missing", name="x")
    assert exc.value.code == RepositoryErrorCode.NOT_FOUND


async def test_update_rejects_missing_category(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="A", amount="1", date="2026-01-01", category_id=cat.id)
    with pytest.raises(RepositoryError) as exc:
        await repo.update(exp.id, category_id="cat-nope")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_delete_removes(session):
    cat = await _make_category(session)
    repo = ExpenseRepository(session)
    exp = await repo.create(name="A", amount="1", date="2026-01-01", category_id=cat.id)
    await repo.delete(exp.id)
    with pytest.raises(RepositoryError):
        await repo.get(exp.id)


async def test_delete_missing(session):
    repo = ExpenseRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.delete("missing")
    assert exc.value.code == RepositoryErrorCode.NOT_FOUND
