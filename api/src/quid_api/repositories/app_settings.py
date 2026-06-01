from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import AppSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


SINGLETON_ID = "singleton"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_currency(value: str) -> str:
    cleaned = value.strip().upper()
    if len(cleaned) != 3 or not cleaned.isalpha():
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Currency must be a 3-letter ISO 4217 code.",
        )
    return cleaned


def _validate_categorize_model(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Categorisation model must not be empty.",
        )
    return cleaned


class AppSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> AppSettings:
        row = await self.session.get(AppSettings, SINGLETON_ID)
        if row is None:
            row = AppSettings(
                id=SINGLETON_ID,
                currency="GBP",
                show_importance_badge=True,
                ai_categorize_enabled=True,
                ai_short_names_enabled=True,
                categorize_model="google/gemini-2.5-flash",
                updated_at=_now_iso(),
            )
            self.session.add(row)
            await self.session.flush()
        return row

    async def update(
        self,
        *,
        currency: str | None = None,
        show_importance_badge: bool | None = None,
        ai_categorize_enabled: bool | None = None,
        ai_short_names_enabled: bool | None = None,
        categorize_model: str | None = None,
    ) -> AppSettings:
        row = await self.get()
        changed = False
        if currency is not None:
            row.currency = _validate_currency(currency)
            changed = True
        if show_importance_badge is not None:
            row.show_importance_badge = show_importance_badge
            changed = True
        if ai_categorize_enabled is not None:
            row.ai_categorize_enabled = ai_categorize_enabled
            changed = True
        if ai_short_names_enabled is not None:
            row.ai_short_names_enabled = ai_short_names_enabled
            changed = True
        if categorize_model is not None:
            row.categorize_model = _validate_categorize_model(categorize_model)
            changed = True
        if changed:
            row.updated_at = _now_iso()
            await self.session.flush()
        return row
