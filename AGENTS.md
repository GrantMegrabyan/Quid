# Project instructions

## Workflow

- Treat this as a shared worktree. Do not revert or overwrite changes you did not make.
- Commit after each meaningful chunk of work unless the user asks not to commit. Keep commits focused and inspect `git status`/`git diff` before committing.
- Keep this file updated when new project-specific context, workflows, or constraints are discovered during sessions.
- Ask before destructive or shared-impact operations, especially database wipes, branch resets, force pushes, or deleting files.
- Prefer small, direct changes that match existing patterns over broad refactors.

## Repository layout

- `api/` is the FastAPI + SQLite backend. Python tooling is managed with `uv`.
- `webui/` is the SvelteKit frontend. JavaScript tooling is managed with `npm`.
- Default API database: `api/.data/quid.db` via `QUID_DATABASE_URL=sqlite+aiosqlite:///./.data/quid.db`.
- E2E tests use `api/.data/quid-e2e.db`; do not point e2e runs at the dev/default database.

## Backend notes

- Run backend commands from `api/`.
- Common verification:
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy`
  - `uv run pytest`
- Use Alembic migrations for schema changes under `api/alembic/versions/`.
- Transactions are represented as `expenses` in the schema/code.
- Use `uv run quid-api clear-transactions` for the built-in transaction wipe, but only after explicit confirmation.

## Frontend notes

- Run frontend commands from `webui/`.
- Common verification:
  - `npm run check`
  - `npm run build`
  - `npm run test:e2e` when user-facing behavior changes and a browser check is needed.
- `npm run format` currently may fail if Prettier/Tailwind looks for `src/routes/layout.css`; do not assume formatting failures are caused by the current change without reading the output.

## Category/AI categorisation context

- Default categories live in both `api/src/quid_api/seed.py` and `webui/src/lib/repos/seed.ts`; keep them aligned.
- Category descriptions are sent to AI categorisation. Keep descriptions concise and include both “belongs here” and “does not include” guidance when useful.
- AI categorisation should strongly prefer existing categories and only create a new category when no existing guided category reasonably fits.
