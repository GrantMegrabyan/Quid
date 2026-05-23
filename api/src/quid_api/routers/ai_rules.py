from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response, status

from quid_api.db import get_session
from quid_api.repositories.ai_rules import AiRuleRepository
from quid_api.schemas import AiRuleCreate, AiRuleOut, AiRuleUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/ai-rules", tags=["ai-rules"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@router.get("", response_model=list[AiRuleOut])
async def list_ai_rules(session: SessionDep) -> list[AiRuleOut]:
    repo = AiRuleRepository(session)
    return [AiRuleOut.model_validate(r) for r in await repo.list_all()]


@router.get("/{rule_id}", response_model=AiRuleOut)
async def get_ai_rule(rule_id: str, session: SessionDep) -> AiRuleOut:
    repo = AiRuleRepository(session)
    return AiRuleOut.model_validate(await repo.get(rule_id))


@router.post("", response_model=AiRuleOut, status_code=status.HTTP_201_CREATED)
async def create_ai_rule(payload: AiRuleCreate, session: SessionDep) -> AiRuleOut:
    repo = AiRuleRepository(session)
    rule = await repo.create(**payload.model_dump())
    await session.commit()
    return AiRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=AiRuleOut)
async def update_ai_rule(rule_id: str, payload: AiRuleUpdate, session: SessionDep) -> AiRuleOut:
    repo = AiRuleRepository(session)
    rule = await repo.update(rule_id, **payload.model_dump(exclude_unset=True))
    await session.commit()
    return AiRuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_rule(rule_id: str, session: SessionDep) -> Response:
    repo = AiRuleRepository(session)
    await repo.delete(rule_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
