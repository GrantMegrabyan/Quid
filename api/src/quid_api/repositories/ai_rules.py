from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import AiRule

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AiInstruction:
    id: str
    text: str


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(text: str | None) -> str:
    cleaned = (text or "").strip()
    if cleaned == "":
        raise RepositoryError(RepositoryErrorCode.VALIDATION, "AI rule text cannot be blank.")
    return cleaned


class AiRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, *, enabled_only: bool = False) -> list[AiRule]:
        stmt = select(AiRule).order_by(AiRule.priority, AiRule.created_at, AiRule.id)
        if enabled_only:
            stmt = stmt.where(AiRule.enabled.is_(True))
        return list((await self.session.scalars(stmt)).all())

    async def instructions(self) -> list[AiInstruction]:
        return [
            AiInstruction(id=rule.id, text=rule.text)
            for rule in await self.list_all(enabled_only=True)
        ]

    async def get(self, rule_id: str) -> AiRule:
        row = await self.session.get(AiRule, rule_id)
        if row is None:
            raise RepositoryError(RepositoryErrorCode.NOT_FOUND, f"AI rule not found: {rule_id}")
        return row

    async def create(self, *, text: str, enabled: bool, priority: int) -> AiRule:
        row = AiRule(
            id=f"ai-rule-{uuid4()}",
            text=_clean_text(text),
            enabled=enabled,
            priority=priority,
            created_at=_now_iso(),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, rule_id: str, **patch: object) -> AiRule:
        row = await self.get(rule_id)
        for key, value in patch.items():
            if key == "text":
                value = _clean_text(str(value) if value is not None else None)
            setattr(row, key, value)
        await self.session.flush()
        return row

    async def delete(self, rule_id: str) -> None:
        row = await self.get(rule_id)
        await self.session.delete(row)
        await self.session.flush()
