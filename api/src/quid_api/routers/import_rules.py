from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response, status

from quid_api.db import get_session
from quid_api.repositories.import_rules import ImportRuleRepository
from quid_api.schemas import (
    ImportRuleApplyResponse,
    ImportRuleCreate,
    ImportRuleOut,
    ImportRuleUpdate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/import-rules", tags=["import-rules"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@router.get("", response_model=list[ImportRuleOut])
async def list_import_rules(session: SessionDep) -> list[ImportRuleOut]:
    repo = ImportRuleRepository(session)
    return [ImportRuleOut.model_validate(r) for r in await repo.list_all()]


@router.get("/{rule_id}", response_model=ImportRuleOut)
async def get_import_rule(rule_id: str, session: SessionDep) -> ImportRuleOut:
    repo = ImportRuleRepository(session)
    return ImportRuleOut.model_validate(await repo.get(rule_id))


@router.post("", response_model=ImportRuleOut, status_code=status.HTTP_201_CREATED)
async def create_import_rule(payload: ImportRuleCreate, session: SessionDep) -> ImportRuleOut:
    repo = ImportRuleRepository(session)
    rule = await repo.create(**payload.model_dump())
    await session.commit()
    return ImportRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=ImportRuleOut)
async def update_import_rule(
    rule_id: str, payload: ImportRuleUpdate, session: SessionDep
) -> ImportRuleOut:
    repo = ImportRuleRepository(session)
    rule = await repo.update(rule_id, **payload.model_dump(exclude_unset=True))
    await session.commit()
    return ImportRuleOut.model_validate(rule)


@router.post("/{rule_id}/apply", response_model=ImportRuleApplyResponse)
async def apply_import_rule(rule_id: str, session: SessionDep) -> ImportRuleApplyResponse:
    repo = ImportRuleRepository(session)
    result = await repo.apply_to_existing(rule_id)
    await session.commit()
    return ImportRuleApplyResponse(
        matched=result.matched,
        updated=result.updated,
        deleted=result.deleted,
    )


@router.post("/apply-all", response_model=ImportRuleApplyResponse)
async def apply_all_import_rules(session: SessionDep) -> ImportRuleApplyResponse:
    repo = ImportRuleRepository(session)
    result = await repo.apply_all_to_existing()
    await session.commit()
    return ImportRuleApplyResponse(
        matched=result.matched,
        updated=result.updated,
        deleted=result.deleted,
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import_rule(rule_id: str, session: SessionDep) -> Response:
    repo = ImportRuleRepository(session)
    await repo.delete(rule_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
