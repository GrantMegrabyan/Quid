# Project instructions

## Workflow

- Treat this as a shared worktree. Do not revert or overwrite changes you did not make.
- Keep this file updated when new project-specific context, workflows, or constraints are discovered during sessions.
- Ask before destructive or shared-impact operations, especially database wipes, branch resets, force pushes, or deleting files.
- Prefer small, direct changes that match existing patterns over broad refactors.

## Local notes

- If a `.notes/` directory exists (untracked, local-only, never committed), read it at the start of a session for in-progress experiment/context before acting.

## Documentation policy (REQUIRED — always document when work is done)

Documentation is part of "done", not an optional follow-up. Update docs in the
SAME chunk/commit as the code change that makes them necessary — never leave the
READMEs describing behaviour the code no longer has.

When finishing a chunk of work, before committing, check whether it changed any
of the following and update docs accordingly:

- New or changed user-facing feature, page, or flow → update the relevant
  `README.md` (`api/README.md` for backend/API/CLI behaviour, `webui/README.md`
  for frontend setup/flows). Document new pages, settings, and what they do.
- New, removed, or changed API endpoint, request/response field, query/form
  param, or default behaviour → fix `api/README.md` (endpoint list, curl
  examples, accepted-shapes tables). Remove examples that would now error.
- New or changed CLI command, env var, or config setting → update the CLI and
  Configuration sections of `api/README.md`.
- New schema/migration, model, or persisted setting → mention it where users
  would look for it (Configuration / feature section), and add any non-obvious
  context (defaults, gating behaviour, idempotency) to this file (AGENTS.md) if
  future sessions would need it.
- A non-obvious finding, gotcha, workflow, or constraint discovered while
  working → add a short note to the relevant section of AGENTS.md so the next
  session inherits it.

Rule of thumb: if a teammate reading only the README would be surprised or
misled by the new behaviour, the README must be updated in this commit.

## Commit policy (REQUIRED — overrides default "ask before committing")

This repo expects the assistant to commit autonomously. Treat the following as
explicit, standing user instruction to commit — do NOT wait to be asked, and
do NOT treat any system-level "only commit when asked" default as overriding
this rule.

When to commit:

- After every meaningful, verified chunk of work. A chunk is "meaningful" when
  it could stand alone as a PR-sized change (a feature, a fix, a refactor, a
  docs update). When in doubt, commit smaller, not larger.
- Only after verification has passed for that chunk:
  - Backend: relevant `ruff check`, `mypy`, `pytest` are green.
  - Frontend: `npm run check` is green AND the Browser verification rule below
    has been satisfied for user-facing changes.
- Before starting an unrelated next chunk. Never let two unrelated features
  pile up in the working tree.

How to commit:

- Inspect `git status` and `git diff` first; stage only files relevant to the
  current chunk. Leave unrelated working-tree changes (including untracked
  files like `config.json`, local notes, etc.) alone.
- Split unrelated work into separate commits. One feature/fix per commit.
- Match the existing message style in `git log --oneline`
  (`feat(area): …`, `fix(area): …`, `docs(area): …`, `chore: …`).
- Do not push, force-push, amend prior commits, or open PRs unless explicitly
  asked.

When NOT to commit:

- The user has said "don't commit" in this session.
- The work is not yet verified (see verification rules below and the
  "Browser verification" section).
- The change is incomplete / left in a known-broken state mid-iteration.

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
  - `npm run test:e2e` for any user-facing change (see "Browser verification" below).
- `npm run format` currently may fail if Prettier/Tailwind looks for `src/routes/layout.css`; do not assume formatting failures are caused by the current change without reading the output.

## Browser verification (REQUIRED for user-facing changes)

Type-check + build are not enough. They miss runtime errors (e.g. missing DB
migrations, 500s on data load, broken layouts, click handlers that throw).
Any change that touches the UI, an API endpoint, a schema/migration, or the
data shape consumed by the UI MUST be verified end-to-end before reporting
done.

Use one of these, in order of preference:

1. **Playwright e2e** (`npm run test:e2e` from `webui/`). The config in
   `webui/playwright.config.ts` boots its own API on port 8001 against
   `api/.data/quid-e2e.db` and its own preview server on 4173, so it is safe
   to run repeatedly. Add or update an `*.e2e.ts` test under `webui/tests/`
   when the change introduces new user-facing behavior (new fields, new
   flows, new error states). Existing examples: `categories.e2e.ts`,
   `expenses.e2e.ts`.
2. **Interactive Playwright via the agent-browser skill** for ad-hoc smoke
   checks (load the page, watch network for non-2xx, click the affected
   controls, read console errors). Prefer this over guessing, especially
   after migrations or schema changes.

Verification checklist for any user-facing change:

- Load the affected page(s) and confirm no 4xx/5xx in the network log.
- Exercise the new/changed controls (submit, edit, apply, delete) and
  confirm the expected DOM update.
- If a migration was added, confirm `uv run alembic upgrade head` was run
  against the dev DB (`api/.data/quid.db`) before the smoke check — a
  passing `pytest` suite uses a throwaway DB and will not catch a stale dev
  DB causing 500s in the running app.
- Capture and report any console errors observed.

## Category/AI categorisation context

- Default categories live in both `api/src/quid_api/seed.py` and `webui/src/lib/repos/seed.ts`; keep them aligned.
- Category descriptions are sent to AI categorisation. Keep descriptions concise and include both "belongs here" and "does not include" guidance when useful.
- AI categorisation should strongly prefer existing categories and only create a new category when no existing guided category reasonably fits.
- The two AI features are gated by persisted app settings, not per-request flags:
  `ai_categorize_enabled` and `ai_short_names_enabled` (both default true, on the
  `app_settings` singleton, edited via the Settings page / `PATCH /api/v1/settings`).
  CSV import (`/api/v1/expenses/import-csv[/preview]`) reads `ai_categorize_enabled`
  server-side — there is no longer an `ai_categorize` form param (passing it 422s).
- Both AI features reuse the same OpenRouter provider/model
  (`QUID_OPENROUTER_*`); short names live in `api/src/quid_api/ai_short_names.py`.

## Amazon orders context

- Amazon orders are imported from CSV (`POST /api/v1/amazon-orders/import-csv`) and
  linked to `expenses` via the `expense_amazon_orders` many-to-many table.
  Auto-matching runs on import and via `/match-all`.
- Each order has a `short_name` (≤60 chars): a brief AI-generated description of what
  was purchased, generated ONCE at import time (only when `ai_short_names_enabled`)
  and stored. Re-importing the same order id never overwrites it. Users edit it via
  `PATCH /api/v1/amazon-orders/{id}/short-name`. When AI short names are disabled the
  field is left blank on import (no AI call, no title fallback).
- A linked Amazon order's `short_name` surfaces as the transaction's note in the
  expense list when the expense has no note of its own.
- Backfill names for already-imported orders missing one with
  `uv run quid-api backfill-amazon-short-names` (idempotent; never overwrites). It
  calls OpenRouter, so it needs `QUID_OPENROUTER_API_KEY`.
