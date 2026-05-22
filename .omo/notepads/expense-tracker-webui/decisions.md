## 2026-05-20 Task: orchestration-init
- Execute plan directly in current project directory; no worktree path is present in `.omo/boulder.json`.
- Category names are case-insensitively unique after trimming, per plan default.
- `Uncategorized` is seeded, neutral, non-deletable; deleting other categories cascades expenses to `UNCATEGORIZED_ID`.

## 2026-05-22 Task: fastapi-api-integration
- API lives as a standalone `api/` uv project using FastAPI, async SQLAlchemy, Alembic, SQLite, pydantic v2, Typer, ruff, and strict mypy.
- The webui no longer talks to mock repositories by default; stores import the HTTP repository barrel and use `VITE_API_BASE_URL` for the API base URL.
- CSV import is exposed as `POST /api/v1/expenses/bulk` and as `uv run quid-api import-csv`; the April 2026 CSVs contain 196 rows total.
- The dev database target for manual QA is `api/.data/quid-dev.db`; Playwright uses isolated `api/.data/quid-e2e.db` with `QUID_TESTING=1`.
- Playwright runs against `npm run build && npm run preview` plus a live API server, with `workers: 1` to keep DB resets deterministic.
