from __future__ import annotations

import pytest

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.categories import CategoryRepository


async def test_list_starts_with_only_uncategorized(session):
    repo = CategoryRepository(session)
    rows = await repo.list_all()
    assert [c.id for c in rows] == ["uncategorized"]


async def test_create_assigns_id_color_icon(session):
    repo = CategoryRepository(session)
    cat = await repo.create(name="Groceries")
    assert cat.id.startswith("cat-")
    assert cat.name == "Groceries"
    assert cat.color.startswith("#")
    assert cat.icon == "circle-help"


async def test_create_with_explicit_color_and_icon(session):
    repo = CategoryRepository(session)
    cat = await repo.create(name="Coffee", color="#123456", icon="car-taxi-front")
    assert cat.color == "#123456"
    assert cat.icon == "car-taxi-front"


async def test_create_strips_whitespace(session):
    repo = CategoryRepository(session)
    cat = await repo.create(name="  Bills  ")
    assert cat.name == "Bills"


async def test_create_rejects_blank_name(session):
    repo = CategoryRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="   ")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_create_rejects_case_insensitive_duplicate(session):
    repo = CategoryRepository(session)
    await repo.create(name="Groceries")
    with pytest.raises(RepositoryError) as exc:
        await repo.create(name="  groceries  ")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_get_missing_raises_not_found(session):
    repo = CategoryRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.get("cat-missing")
    assert exc.value.code == RepositoryErrorCode.NOT_FOUND


async def test_update_changes_fields(session):
    repo = CategoryRepository(session)
    cat = await repo.create(name="Groceries")
    updated = await repo.update(cat.id, name="Food", color="#ffaa00", icon="utensils")
    assert updated.name == "Food"
    assert updated.color == "#ffaa00"
    assert updated.icon == "utensils"


async def test_update_uncategorized_rename_rejected(session):
    repo = CategoryRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.update("uncategorized", name="Misc")
    assert exc.value.code == RepositoryErrorCode.IMMUTABLE


async def test_update_uncategorized_with_same_name_ok(session):
    repo = CategoryRepository(session)
    updated = await repo.update("uncategorized", name="Uncategorized", color="#777777")
    assert updated.color == "#777777"


async def test_update_can_change_uncategorized_color_and_icon(session):
    repo = CategoryRepository(session)
    updated = await repo.update("uncategorized", color="#abcdef", icon="wallet")
    assert updated.color == "#abcdef"
    assert updated.icon == "wallet"


async def test_update_rejects_duplicate_name(session):
    repo = CategoryRepository(session)
    a = await repo.create(name="A")
    await repo.create(name="B")
    with pytest.raises(RepositoryError) as exc:
        await repo.update(a.id, name="b")
    assert exc.value.code == RepositoryErrorCode.VALIDATION


async def test_update_missing_raises_not_found(session):
    repo = CategoryRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.update("cat-missing", name="X")
    assert exc.value.code == RepositoryErrorCode.NOT_FOUND


async def test_delete_uncategorized_rejected(session):
    repo = CategoryRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.delete("uncategorized")
    assert exc.value.code == RepositoryErrorCode.IMMUTABLE


async def test_delete_missing_raises_not_found(session):
    repo = CategoryRepository(session)
    with pytest.raises(RepositoryError) as exc:
        await repo.delete("cat-missing")
    assert exc.value.code == RepositoryErrorCode.NOT_FOUND


async def test_delete_removes_row(session):
    repo = CategoryRepository(session)
    cat = await repo.create(name="Temp")
    await repo.delete(cat.id)
    rows = await repo.list_all()
    assert cat.id not in [c.id for c in rows]
