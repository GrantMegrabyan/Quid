"""Persistence for the on-demand Analytics AI narrative.

This is deliberately the ONLY write path in the analytics layer; the
aggregation repository (``repositories/analytics.py``) stays read-only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from quid_api.models import AnalyticsNarrative

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AnalyticsNarrativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest(self) -> AnalyticsNarrative | None:
        stmt = select(AnalyticsNarrative).order_by(AnalyticsNarrative.month.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, *, month: str, content: str, model: str) -> AnalyticsNarrative:
        stmt = select(AnalyticsNarrative).where(AnalyticsNarrative.month == month)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = AnalyticsNarrative(
                id=str(uuid4()),
                month=month,
                content=content,
                generated_at=_now_iso(),
                model=model,
            )
            self.session.add(row)
        else:
            row.content = content
            row.model = model
            row.generated_at = _now_iso()
        await self.session.flush()
        return row
