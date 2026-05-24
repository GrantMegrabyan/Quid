from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends

from quid_api.db import get_session
from quid_api.repositories.import_log import ImportLogRepository
from quid_api.schemas import ImportLogOut

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/import-logs", tags=["import-logs"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@router.get("", response_model=list[ImportLogOut])
async def list_import_logs(session: SessionDep) -> list[ImportLogOut]:
    repo = ImportLogRepository(session)
    return [ImportLogOut.model_validate(r) for r in await repo.list_recent()]
