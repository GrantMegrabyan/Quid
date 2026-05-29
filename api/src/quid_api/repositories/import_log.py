from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from quid_api.models import ImportLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ImportLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        files: list[str],
        imported: int,
        updated: int,
        skipped_duplicates: int,
        skipped_excluded: int,
        skipped_invalid_rows: int,
        source: str = "csv",
        raw_input: str | None = None,
    ) -> ImportLog:
        row = ImportLog(
            id=f"import-log-{uuid4()}",
            imported_at=_now_iso(),
            source=source,
            files=json.dumps(files),
            raw_input=raw_input,
            imported=imported,
            updated=updated,
            skipped_duplicates=skipped_duplicates,
            skipped_excluded=skipped_excluded,
            skipped_invalid_rows=skipped_invalid_rows,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_recent(self, *, limit: int = 50) -> list[ImportLog]:
        stmt = (
            select(ImportLog)
            .order_by(ImportLog.imported_at.desc(), ImportLog.id.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())
