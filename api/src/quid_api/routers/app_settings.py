from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends

from quid_api.db import get_session
from quid_api.repositories.app_settings import AppSettingsRepository
from quid_api.schemas import AppSettingsOut, AppSettingsUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]


@router.get("", response_model=AppSettingsOut)
async def get_app_settings(session: SessionDep) -> AppSettingsOut:
    repo = AppSettingsRepository(session)
    row = await repo.get()
    await session.commit()
    return AppSettingsOut.model_validate(row)


@router.patch("", response_model=AppSettingsOut)
async def update_app_settings(payload: AppSettingsUpdate, session: SessionDep) -> AppSettingsOut:
    repo = AppSettingsRepository(session)
    row = await repo.update(**payload.model_dump(exclude_unset=True))
    await session.commit()
    return AppSettingsOut.model_validate(row)
