"""Importance triage: label the merchants that carry the most spend.

With no hand-set importance anywhere, the whole history is unattributed and
nothing can be learned from it. Rather than wait for the user to correct
transactions one at a time, this ranks merchants with no label yet by total
spend, so a handful of decisions covers the majority of the money.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query

from quid_api.db import get_session
from quid_api.repositories.importance import ImportanceCoverage, ImportanceRepository
from quid_api.schemas import (
    ImportanceCoverageOut,
    ImportanceTriageRequest,
    ImportanceTriageResponse,
    ImportanceTriageResult,
    TriageMerchantOut,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/importance", tags=["importance"])

SessionDep = Annotated["AsyncSession", Depends(get_session)]

_DEFAULT_LIMIT = 20


def _coverage_out(coverage: ImportanceCoverage) -> ImportanceCoverageOut:
    return ImportanceCoverageOut.model_validate(coverage, from_attributes=True)


@router.get("/triage", response_model=ImportanceTriageResponse)
async def get_triage_queue(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = _DEFAULT_LIMIT,
) -> ImportanceTriageResponse:
    repo = ImportanceRepository(session)
    merchants = await repo.triage_queue(limit=limit)
    coverage = await repo.coverage()
    return ImportanceTriageResponse(
        merchants=[
            TriageMerchantOut.model_validate(merchant, from_attributes=True)
            for merchant in merchants
        ],
        coverage=_coverage_out(coverage),
    )


@router.post("/triage", response_model=ImportanceTriageResult)
async def apply_triage(
    payload: ImportanceTriageRequest, session: SessionDep
) -> ImportanceTriageResult:
    """Label every transaction of one merchant, and record the decision.

    Retroactive by design — it is the only way existing history gets labelled —
    but a transaction already marked ``manual`` is left alone: a per-transaction
    decision is more specific than a merchant-wide one.
    """
    repo = ImportanceRepository(session)
    updated = await repo.apply_triage(key=payload.merchant_key, importance=payload.importance)
    coverage = await repo.coverage()
    await session.commit()
    return ImportanceTriageResult(updated=updated, coverage=_coverage_out(coverage))
