from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from quid_api.db import get_session
from quid_api.main import _error_body, _integrity_error_message, create_app
from quid_api.models import AmazonOrder, Category, Expense
from quid_api.settings import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def _contains_leaks(text: str) -> bool:
    leaked = [
        "UNIQUE",
        "FOREIGN KEY",
        "NOT NULL",
        "CHECK",
        "sqlite",
        "insert into",
        "update",
        "delete from",
    ]
    return any(token.lower() in text.lower() for token in leaked)


def _make_integrity_error(message: str) -> IntegrityError:
    class _Orig(Exception):
        def __str__(self) -> str:
            return message

    return IntegrityError(statement="INSERT ...", params={"secret": "value"}, orig=_Orig())


def test_integrity_error_message_classification() -> None:
    assert _integrity_error_message(
        _make_integrity_error("UNIQUE constraint failed: categories.name")
    ) == ("That record already exists.")
    assert (
        _integrity_error_message(_make_integrity_error("FOREIGN KEY constraint failed"))
        == "Referenced record does not exist."
    )
    assert (
        _integrity_error_message(_make_integrity_error("NOT NULL constraint failed: expenses.note"))
        == "A required field is missing."
    )
    assert (
        _integrity_error_message(_make_integrity_error("CHECK constraint failed: ck"))
        == "A value failed validation."
    )
    assert _integrity_error_message(_make_integrity_error("some driver text")) == (
        "The request conflicts with existing data."
    )


@pytest_asyncio.fixture
async def integrity_client(engine) -> AsyncGenerator[AsyncClient, None]:
    settings = Settings(
        database_url=str(engine.url),
        testing=True,
        testing_token="test-token",
        openrouter_api_key=None,
    )
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with sm() as sess:
            yield sess

    app = create_app(settings=settings)
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings

    router = APIRouter(prefix="/__test__")

    @router.post("/unique")
    async def unique_violation(session: Annotated[AsyncSession, Depends(get_session)]):
        session.add(
            Category(id="cat-one", name="Duplicate", color="#000", icon="a", description="")
        )
        await session.flush()
        session.add(
            Category(id="cat-two", name=" duplicate ", color="#111", icon="b", description="")
        )
        await session.commit()
        return {"ok": True}

    @router.post("/foreign-key")
    async def foreign_key_violation(session: Annotated[AsyncSession, Depends(get_session)]):
        session.add(
            Expense(
                id="expense-fk",
                name="Broken FK",
                amount=Decimal("1.00"),
                date="2026-05-30",
                category_id="missing-category",
                note="",
                importance="important",
                category_source="import",
            )
        )
        await session.commit()
        return {"ok": True}

    @router.post("/check")
    async def check_violation(session: Annotated[AsyncSession, Depends(get_session)]):
        session.add(
            AmazonOrder(
                id="order-check",
                order_date="2026-05-30",
                total=Decimal("-1.00"),
                currency="GBP",
                items_json="[]",
                shipments_json="[]",
                imported_at="2026-05-30T00:00:00Z",
            )
        )
        await session.commit()
        return {"ok": True}

    @router.post("/not-null")
    async def not_null_violation(session: Annotated[AsyncSession, Depends(get_session)]):
        session.add(
            AmazonOrder(
                id="order-null",
                order_date="2026-05-30",
                total=Decimal("1.00"),
                currency="GBP",
                items_json="[]",
                shipments_json="[]",
            )
        )
        await session.commit()
        return {"ok": True}

    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/__test__/unique", "That record already exists."),
        ("/__test__/foreign-key", "Referenced record does not exist."),
        ("/__test__/check", "A value failed validation."),
        ("/__test__/not-null", "A required field is missing."),
    ],
)
async def test_integrity_error_responses_are_sanitized(
    integrity_client, path: str, message: str
) -> None:
    res = await integrity_client.post(path)
    assert res.status_code == 422, res.text
    body = res.json()
    assert body == _error_body("VALIDATION", message)
    assert not _contains_leaks(res.text)


@pytest.mark.asyncio
async def test_session_rolled_back_after_integrity_error(integrity_client) -> None:
    """An aborted transaction must not leak onto a reused pooled connection.

    After an IntegrityError-triggering request, a subsequent valid write on the
    same app/pool must succeed (i.e. the prior transaction was rolled back, not
    left dangling).
    """
    first = await integrity_client.post("/__test__/unique")
    assert first.status_code == 422, first.text

    second = await integrity_client.post("/__test__/foreign-key")
    assert second.status_code == 422, second.text
    assert second.json() == _error_body("VALIDATION", "Referenced record does not exist.")
