# Plan: Quid API (FastAPI + SQLite + webui integration)

**Created**: 2026-05-22
**Owner**: Sisyphus (overnight autonomous execution)
**Status**: pending Momus review

---

## 1. Goal

Build a real backend for the existing SvelteKit expense tracker (`webui/`), replace the in-browser mocks with HTTP-backed repositories, and re-point the existing Playwright e2e suite at the live API.

**Definition of done (single sentence)**: From a fresh clone, a developer can run `uv run quid-api migrate && uv run quid-api seed && uv run quid-api serve` in one terminal and `npm --prefix webui run dev` in another and use the app end-to-end with all expense/category state persisting in SQLite; `npm --prefix webui run test:e2e` passes against the live API with no mock involvement.

---

## 2. Non-goals (explicit)

- Authentication / users / multi-tenancy
- Pagination cursors / search / filtering beyond `limit` + `offset` on expenses
- Currency handling (server stores plain decimals; webui formats as GBP at the edge)
- Docker / docker-compose / deployment artefacts
- Production logging, metrics, tracing
- WebSocket / SSE / live-update channels
- Migrating any data out of the current localStorage store (greenfield API; localStorage is dev-only)

---

## 3. Tech stack (locked)

| Concern | Choice | Notes |
|---|---|---|
| Python | 3.12 | uv-managed |
| Web framework | FastAPI (latest stable) | async routes throughout |
| ASGI server | uvicorn (`[standard]` extras) | dev + prod entrypoint |
| ORM | SQLAlchemy 2.0 async | `aiosqlite` driver |
| Migrations | Alembic | first migration includes `Uncategorized` data row |
| Validation | pydantic v2 + pydantic-settings | request/response models distinct from ORM |
| CLI | typer | `migrate`, `seed`, `serve` subcommands |
| Tests | pytest + pytest-asyncio + httpx.AsyncClient | per-test transactional rollback against a temp-file SQLite |
| Lint/format | ruff (lint + format) | replaces black + isort + flake8 |
| Type check | **mypy --strict** | non-negotiable per user decision |
| Coverage | pytest-cov | target ≥85% on `src/quid_api/` |
| Package manager | uv | `uv sync`, `uv run`, `uv add` |

---

## 4. Repository layout

```
quid/
├── .gitignore              (existing)
├── api/                    (NEW — standalone uv project)
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── README.md
│   ├── .python-version     ("3.12")
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema_and_uncategorized.py
│   ├── src/
│   │   └── quid_api/
│   │       ├── __init__.py
│   │       ├── main.py              (FastAPI app factory + ASGI entry)
│   │       ├── cli.py               (typer CLI: migrate/seed/serve)
│   │       ├── settings.py          (pydantic-settings)
│   │       ├── db.py                (engine, session factory, get_session dep)
│   │       ├── models.py            (SQLAlchemy ORM: Category, Expense)
│   │       ├── schemas.py           (pydantic request/response models)
│   │       ├── errors.py            (RepositoryError + HTTP exception mapping)
│   │       ├── repositories/
│   │       │   ├── __init__.py
│   │       │   ├── categories.py
│   │       │   └── expenses.py
│   │       ├── routers/
│   │       │   ├── __init__.py
│   │       │   ├── categories.py
│   │       │   ├── expenses.py
│   │       │   └── health.py
│   │       ├── seed.py              (deterministic seed data; called by CLI)
│   │       └── testing.py           (test-only reset hook; gated by env var)
│   └── tests/
│       ├── conftest.py              (async session + AsyncClient fixtures)
│       ├── test_health.py
│       ├── test_categories_repo.py
│       ├── test_expenses_repo.py
│       ├── test_categories_api.py
│       ├── test_expenses_api.py
│       ├── test_cascade_delete.py
│       ├── test_seed.py
│       └── test_cli.py
└── webui/                  (existing — minor additions only)
    ├── playwright.config.ts        (modified: webServer spawns api)
    ├── tests/helpers.ts            (modified: resetDb() hits /testing/reset)
    └── src/lib/repos/
        ├── httpCategoryRepository.ts   (NEW)
        ├── httpExpenseRepository.ts    (NEW)
        ├── httpClient.ts               (NEW)
        └── index.ts                    (modified: export http impls by default)
```

**Rationale**: standalone `api/` uv project keeps Python boundaries clean and lets webui-only developers ignore the backend entirely.

---

## 5. Domain & wire contracts (exact match to webui)

### Category

```json
{ "id": "cat-…", "name": "Groceries", "color": "#…", "icon": "shopping-cart" }
```

- `id` server-generated as `cat-<uuid4>` on create. `'uncategorized'` is reserved.
- `name` trimmed; case-insensitive unique across all categories.
- `color` 7-char hex `#rrggbb`. If client omits/sends empty, server derives from id (port of webui `colorForCategoryId`).
- `icon` normalized through the same allow-list as webui (`normalizeCategoryIcon`); unknown values fall back to `circle-help`.

**Invariants enforced server-side**:
- Cannot delete `id === 'uncategorized'` → 409 `IMMUTABLE`
- Cannot rename `id === 'uncategorized'` (name must stay `"Uncategorized"`) → 409 `IMMUTABLE`
- Duplicate trimmed-lowercased name → 422 `VALIDATION`
- Blank name → 422 `VALIDATION`

### Expense

```json
{ "id": "…", "name": "Whole Foods", "amount": 58.24, "date": "2026-05-22", "categoryId": "cat-…", "note": "" }
```

- `id` server-generated as `<uuid4>` (no prefix) to match `MockExpenseRepository`.
- `amount` positive `number` with at most 2 decimal places.
- `date` `YYYY-MM-DD` (no time, no timezone).
- `categoryId` must reference an existing category; foreign key enforced.
- `note` arbitrary string (may be empty).
- Field naming: **camelCase on the wire** (`categoryId`), regardless of Python snake_case internals. Use pydantic `alias_generator=to_camel` + `populate_by_name=True` to serialize/deserialize cleanly.

### Error response (matches webui `RepositoryError`)

```json
{ "code": "NOT_FOUND" | "IMMUTABLE" | "VALIDATION", "message": "human-readable" }
```

| RepositoryError code | HTTP status |
|---|---|
| `NOT_FOUND` | 404 |
| `IMMUTABLE` | 409 |
| `VALIDATION` | 422 |

FastAPI's default 422 for pydantic validation errors will be re-wrapped to this shape via a global `RequestValidationError` exception handler so the webui sees a single error format.

---

## 6. HTTP routes

All under `/api/v1`. OpenAPI docs at `/docs`. CORS allows `http://localhost:5173` and `http://localhost:4173`.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | — | 200 `{status:"ok"}` | — |
| GET | `/api/v1/categories` | — | 200 `Category[]` | — |
| GET | `/api/v1/categories/{id}` | — | 200 `Category` | 404 |
| POST | `/api/v1/categories` | `Omit<Category,'id'>` | 201 `Category` | 422 |
| PATCH | `/api/v1/categories/{id}` | `Partial<Omit<Category,'id'>>` | 200 `Category` | 404, 409, 422 |
| DELETE | `/api/v1/categories/{id}` | — | 204 | 404, 409 |
| GET | `/api/v1/expenses?limit&offset` | — | 200 `Expense[]` (date DESC) | 422 |
| GET | `/api/v1/expenses/{id}` | — | 200 `Expense` | 404 |
| POST | `/api/v1/expenses` | `Omit<Expense,'id'>` | 201 `Expense` | 422 |
| POST | `/api/v1/expenses/bulk` | `{ items: BulkExpenseInput[] }` | 201 `{created, categoriesCreated, expenses}` | 422 |
| PATCH | `/api/v1/expenses/{id}` | `Partial<Omit<Expense,'id'>>` | 200 `Expense` | 404, 422 |
| DELETE | `/api/v1/expenses/{id}` | — | 204 | 404 |
| POST | `/api/v1/testing/reset` | — | 204 | 404 (only mounted when `QUID_TESTING=1`) |

### 6.1 Bulk import endpoint (`POST /api/v1/expenses/bulk`)

Built specifically to ingest the CSVs under [`cvs/`](file:///Users/grant/dev/quid/cvs/) (and any future bank export with the same shape).

**Request body** (camelCase as elsewhere):

```json
{
  "items": [
    { "name": "Whole Foods", "category": "groceries", "amount": -58.24, "date": "2026-04-03", "note": "" },
    { "name": "Starbucks",   "category": "eating_out", "amount":  10.00, "date": "2026-04-01", "note": "" }
  ]
}
```

`BulkExpenseInput` schema:

| Field | Type | Rules |
|---|---|---|
| `name` | str | trimmed, non-empty |
| `category` | str | slug or display name; mapped per rules below |
| `amount` | Decimal | sign-agnostic on input; stored as `abs(amount)`; `0` → 422 |
| `date` | str | `YYYY-MM-DD` |
| `note` | str | optional, defaults to `""` |

**Category mapping (deterministic)**:

1. Normalise input: `trim().lower()`; replace `_`/`-` with spaces.
2. Look for an existing category whose `name.lower().strip()` equals the normalised input. If found → use it.
3. Else look for an existing category whose `id` equals `cat-<normalised-with-hyphens>`. If found → use it.
4. Else **create** a new category in-transaction:
   - `id = cat-<slug>` (lowercase, `_`→`-`, spaces→`-`)
   - `name = Title Case` of slug words (e.g. `eating_out` → `Eating Out`)
   - `color` derived via the existing `colorForCategoryId` port
   - `icon = circle-help`
5. Special case: `category` literal `"other"` → maps to `'uncategorized'` (existing seed row).

**Amount handling**: `abs(amount)`. Rationale: bank exports use signed amounts (debit negative, credit positive), but this app records expenses as positive magnitudes. The webui `Expense.amount > 0` invariant must hold. Income-tracking is out of scope — `amount == 0` is rejected as nonsensical.

**Transactional semantics**: the entire payload is processed inside one `async with session.begin():` block. If any item fails validation (blank name, bad date, amount==0, etc.), the whole import rolls back and the response is 422 with `{ code: "VALIDATION", message: "row N: <reason>" }`. No partial success.

**Response** (201):

```json
{
  "created": 194,
  "categoriesCreated": [{"id": "cat-car", "name": "Car", ...}, ...],
  "expenses": [/* all created expense rows in input order */]
}
```

**Limits**: max 5,000 items per request (guards against runaway payloads); enforce in the schema.

**PATCH semantics**: pydantic `exclude_unset=True` → only present fields are applied. `null` is rejected for required fields, accepted for nullable (none currently).

**List sorting**: hard-coded `ORDER BY date DESC, id DESC` to match `mockExpenseRepository.byDateDesc` and provide stable pagination.

---

## 7. Database schema

```sql
CREATE TABLE categories (
  id    TEXT PRIMARY KEY,
  name  TEXT NOT NULL,
  color TEXT NOT NULL,
  icon  TEXT NOT NULL
);
CREATE UNIQUE INDEX ix_categories_name_ci ON categories (lower(trim(name)));

CREATE TABLE expenses (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  amount      NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  date        TEXT NOT NULL,   -- YYYY-MM-DD; SQLite has no native DATE
  category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE SET DEFAULT,
  note        TEXT NOT NULL DEFAULT '',
  CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);
CREATE INDEX ix_expenses_date ON expenses (date);
CREATE INDEX ix_expenses_category ON expenses (category_id);
```

**Foreign-key enforcement**: SQLite needs `PRAGMA foreign_keys = ON` per connection. Set via SQLAlchemy `event.listens_for(engine.sync_engine, "connect")` hook.

**Cascade-on-category-delete**: cannot use `ON DELETE SET DEFAULT` portably with SQLite + aiosqlite reliably. Implementation: do it in `CategoryRepository.delete()` as a single transaction — `UPDATE expenses SET category_id='uncategorized' WHERE category_id=:id` before `DELETE FROM categories WHERE id=:id`. Verified by `test_cascade_delete.py`.

**Initial migration** (`0001_initial_schema_and_uncategorized.py`) creates the tables AND inserts the single immutable row:

```python
op.execute(
    "INSERT INTO categories (id, name, color, icon) "
    "VALUES ('uncategorized', 'Uncategorized', '#9CA3AF', 'circle-help')"
)
```

This guarantees the cascade target always exists, even before the user runs `seed`.

---

## 8. Settings (env-driven)

```python
class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./.data/quid.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    testing: bool = False             # gates /api/v1/testing/reset
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_prefix="QUID_", env_file=".env", extra="ignore")
```

`.env.example` checked in, `.env` ignored. `api/.data/` added to api-level `.gitignore`.

---

## 9. CLI (typer)

```
uv run quid-api migrate                    # alembic upgrade head
uv run quid-api migrate --down N           # alembic downgrade -N
uv run quid-api seed                       # add 5 sample categories + 17 sample expenses
uv run quid-api seed --reset               # truncate (except Uncategorized) then re-seed
uv run quid-api import-csv <path>...       # parse CSV(s) and POST to /expenses/bulk
uv run quid-api serve                      # uvicorn quid_api.main:app --reload
uv run quid-api serve --no-reload --host 0.0.0.0 --port 8000
```

`seed` is **idempotent in default mode**: if a sample category already exists (by id), skip it; same for sample expenses. `--reset` is the only way to wipe.

`import-csv` accepts one or more CSV file paths with columns `name,category,amount,date,note` (header required). It batches each file into a single `POST /api/v1/expenses/bulk` call. Connects to the URL in `--api-url` (default `http://localhost:8000`). Used to load the [`cvs/`](file:///Users/grant/dev/quid/cvs/) bank exports as part of Phase 4b below.

---

## 10. Testing strategy

### Unit (repositories): `tests/test_*_repo.py`

- Fresh in-memory SQLite per test via fixture; run all migrations in-process before each test.
- Cover: every repo method, every error path (404/409/422), cascade-delete reparenting, uniqueness, immutability.

### Integration (HTTP): `tests/test_*_api.py`

- `httpx.AsyncClient(transport=ASGITransport(app))` against the FastAPI app.
- Per-test temp-file SQLite (not in-memory; aiosqlite + in-memory + multiple connections is brittle).
- Cover: all routes, status codes, error body shape, CORS preflight, OpenAPI schema sanity (response models present).

### Coverage gates

- `pytest --cov=quid_api --cov-fail-under=85`
- Exclusions: `cli.py` interactive paths, `__main__` blocks.

### Webui e2e (Phase 7 below)

- Existing Playwright tests pointed at real API.
- `playwright.config.ts` `webServer` array starts BOTH the api (`uv run --project ../api quid-api serve --no-reload --port 8001`) AND vite, with `QUID_TESTING=1` and an isolated `.data/quid-test.db`.
- `tests/helpers.ts` `resetState()` now POSTs to `http://localhost:8001/api/v1/testing/reset` then calls `seed()` if the test needs sample data. Existing `localStorage.clear()` calls become no-ops (or are removed).
- Webui dev runtime points at `http://localhost:8001` for the test profile via `VITE_API_BASE_URL` env var.

---

## 11. Phased execution

Each phase is independently verifiable and atomically committable. **No phase begins until prior phase's verification passes.**

### Phase 0 — Project scaffolding (commit: `feat(api): scaffold uv project + tooling`)

1. `mkdir api && cd api && uv init --package --python 3.12`
2. `uv add fastapi 'uvicorn[standard]' 'sqlalchemy[asyncio]' aiosqlite alembic 'pydantic[email]' pydantic-settings typer`
3. `uv add --dev pytest pytest-asyncio pytest-cov httpx ruff mypy types-* (as needed)`
4. `pyproject.toml`: configure ruff (line-length 100, select `["E","F","I","UP","B","SIM","RUF"]`), ruff format, mypy `strict=true`, pytest with asyncio mode `auto`.
5. Create empty package skeleton (`src/quid_api/__init__.py`, etc.).
6. `api/README.md` with quickstart.
7. `api/.gitignore`: `.data/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.db`, `*.db-journal`.

**Verify**: `uv sync` succeeds, `uv run ruff check`, `uv run mypy src`, `uv run pytest` (no tests yet → exit 5 OK to ignore at this stage; will pass after Phase 1).

### Phase 1 — DB layer + first migration (commit: `feat(api): sqlalchemy models + initial migration with uncategorized`)

1. `settings.py`, `db.py` (engine + `async_sessionmaker` + `get_session` FastAPI dep + FK-pragma listener).
2. `models.py`: `Category`, `Expense` with `Mapped[...]` annotations.
3. `alembic init alembic` then customise `env.py` for async + target_metadata from models.
4. Author `0001_initial_schema_and_uncategorized.py` (autogenerated then manually augmented with the data INSERT and the case-insensitive index — Alembic autogen doesn't produce expression indexes).
5. Smoke test: `uv run alembic upgrade head` against a temp DB, then `sqlite3` query confirms Uncategorized row.

**Verify**: `uv run mypy src` clean. Smoke script asserts the row exists.

### Phase 2 — Repository layer + repo tests (commit: `feat(api): category + expense repositories with cascade semantics`)

1. `errors.py`: `RepositoryError` class + code enum.
2. `repositories/categories.py`: list/get/create/update/delete with all invariants.
3. `repositories/expenses.py`: list (date DESC + pagination)/get/create/update/delete.
4. Cascade-delete implemented as `UPDATE expenses SET category_id='uncategorized' WHERE category_id=:id` then `DELETE FROM categories WHERE id=:id` inside one transaction.
5. `tests/conftest.py`: async engine fixture, alembic-upgrade-once-per-session, session-per-test with rollback.
6. Tests covering: blank name, duplicate name (case-insens + trim variants), update uncategorized name rejected, delete uncategorized rejected, cascade reparents expenses, missing category fk on expense create → 422, amount ≤ 0 rejected, bad date format rejected.

**Verify**: `uv run pytest tests/test_*_repo.py test_cascade_delete.py -v` all pass; coverage ≥85% for `repositories/`.

### Phase 3 — HTTP routers + integration tests (commit: `feat(api): rest endpoints + error mapping`)

1. `schemas.py`: pydantic models with `to_camel` alias generator + `populate_by_name=True`.
2. `routers/{categories,expenses,health}.py` thin handlers delegating to repos, mapping `RepositoryError → HTTPException`.
3. `main.py`: app factory, CORS middleware, exception handlers (RepositoryError + RequestValidationError → unified body), router registration.
4. `routers/testing.py` (mounted only when `settings.testing`), exposing POST `/api/v1/testing/reset`.
5. Integration tests for every route, including the error-body shape and CORS preflight.

**Verify**: `uv run pytest` full suite green. Manual curl smoke against `uv run quid-api serve` covers list/create/update/delete on both resources.

### Phase 4 — CLI (commit: `feat(api): typer cli for migrate/seed/serve`)

1. `seed.py` port of `webui/src/lib/repos/seed.ts` (idempotent upserts).
2. `cli.py` with typer subcommands; `serve` uses `uvicorn.run` programmatically.
3. `pyproject.toml` `[project.scripts]` entry `quid-api = "quid_api.cli:app"`.
4. `tests/test_cli.py` uses `typer.testing.CliRunner` to verify each subcommand.

**Verify**: `uv run quid-api migrate && uv run quid-api seed` against a fresh `.data/quid.db` succeeds; sqlite3 query confirms 6 categories + 17 expenses.

### Phase 4b — Bulk import + CSV loader (commit: `feat(api): bulk expense import + csv loader`)

1. `schemas.py`: add `BulkExpenseInput` and `BulkExpenseResponse`. Max 5,000 items per request.
2. `repositories/expenses.py`: add `bulk_create(items)` that resolves category names (creating missing ones), abs() amounts, validates each row, and inserts all in one transaction.
3. `routers/expenses.py`: `POST /api/v1/expenses/bulk` handler delegating to the repo.
4. `cli.py`: `import-csv` subcommand using `httpx` to POST to the running server. Logs `created`, `categoriesCreated`, per-file timing.
5. `tests/test_bulk_import.py`: covers transactional rollback on bad row, category creation, slug→name mapping, `other`→`uncategorized`, abs() of negative amounts, 5,001-item rejection.
6. `tests/test_csv_loader.py`: writes a fixture CSV to `tmp_path`, runs the typer CLI against a live FastAPI test server (`uvicorn` in a thread, or `httpx.ASGITransport` for unit-level), asserts counts.

**Verify**:
- All new tests pass.
- Live run: start server, `uv run quid-api import-csv ../cvs/april-2026-grant-monzo.csv ../cvs/april-2026-grant-revolut.csv ../cvs/april-2026-grant-monzo-shared.csv`, confirm exactly **196 expenses** created (monzo 102 + revolut 78 + monzo-shared 16; verified via `awk 'FNR>1' cvs/*.csv | wc -l`) and ~10 new categories. NOTE: monzo files are all-negative debits, revolut all-positive — server abs()es so all 196 are valid positive expenses.
- Capture transcript to `.omo/evidence/api-csv-import.log`.

### Phase 5 — Quality gates + manual smoke (commit: only if anything changed)

1. `uv run ruff check . && uv run ruff format --check .`
2. `uv run mypy src tests` strict-clean (tests get `--strict` too).
3. `uv run pytest --cov` ≥85%.
4. Start server, curl through happy path, capture transcript to `.omo/evidence/api-curl-smoke.log`.

### Phase 6 — Webui HTTP repositories (commit: `feat(webui): http-backed repositories replace mocks`)

1. `webui/src/lib/repos/httpClient.ts`: thin `fetch` wrapper with base URL from `import.meta.env.VITE_API_BASE_URL`, default `http://localhost:8000`, JSON parse/serialize, normalises error response back into `RepositoryError`.
2. `httpCategoryRepository.ts` + `httpExpenseRepository.ts` implementing the existing TS interfaces 1:1.
3. Update [`stores/categories.ts`](file:///Users/grant/dev/quid/webui/src/lib/stores/categories.ts#L2) and [`stores/expenses.ts`](file:///Users/grant/dev/quid/webui/src/lib/stores/expenses.ts#L2) — currently import `categoryRepository` / `expenseRepository` directly from `mockCategoryRepository.js` / `mockExpenseRepository.js`. Repoint imports to the new HTTP repositories. This is the actual swap; `repos/index.ts` is barely used today.
4. `repos/index.ts`: re-export the HTTP impls as canonical `categoryRepository` / `expenseRepository`; keep mocks importable under explicit `mockCategoryRepository` / `mockExpenseRepository` names; don't delete them.
5. Add `webui/.env.example` documenting `VITE_API_BASE_URL`.

**Modified webui files this phase**:
- `webui/src/lib/repos/httpClient.ts` (new)
- `webui/src/lib/repos/httpCategoryRepository.ts` (new)
- `webui/src/lib/repos/httpExpenseRepository.ts` (new)
- `webui/src/lib/repos/index.ts` (modified — barrel export)
- `webui/src/lib/stores/categories.ts` (modified — import swap)
- `webui/src/lib/stores/expenses.ts` (modified — import swap)
- `webui/.env.example` (new)

**Verify**: `npm --prefix webui run check` clean; grep confirms no `mock(Category|Expense)Repository` imports outside `repos/index.ts` and the test helpers. With api+webui both running, manual click-through still works.

### Phase 7 — E2E harness pointed at live API (commit: `test(e2e): point playwright at live api + db reset hook`)

1. Refactor `webui/playwright.config.ts` `webServer` to an array starting api (`QUID_TESTING=1`, isolated `.data/quid-test.db`, port 8001) AND vite (with `VITE_API_BASE_URL=http://localhost:8001`).
2. `tests/helpers.ts`: replace `clearLocalStorage` with `resetServerState()` that POSTs `/api/v1/testing/reset` then re-runs Alembic via the testing endpoint (the reset handler drops + recreates schema + reinserts Uncategorized + optionally re-seeds samples per query param).
3. Each test's `beforeEach` calls `resetServerState({ withSamples: true })`.
4. Delete mock-specific reset code paths; mocks stay as code but aren't exercised by tests.

**Verify**: `npm --prefix webui run test:e2e` green end-to-end with api running. Capture run log to `.omo/evidence/api-e2e-run.txt`.

### Phase 8 — Final verification + handoff notes (commit: `docs(api): readme + handoff notes`)

1. `api/README.md`: quickstart, env vars, CLI ref, troubleshooting, **bulk import + CSV loader docs**.
2. Update `webui/README.md` with the "needs api running on :8000" note.
3. Append a Decisions/Issues entry to `.omo/notepads/expense-tracker-webui/decisions.md` (or create `.omo/notepads/api/decisions.md`) summarising notable choices and any deviations.
4. **Re-run the CSV import against the dev database** (not the test DB) so the user wakes up with `cvs/` data loaded in the app. Capture before/after expense counts.
5. Final all-green run: api tests + webui type-check + webui e2e + screenshot of the live app showing the imported April 2026 expenses on the dashboard.

---

## 12. Verification matrix (per phase, before commit)

| Check | Command | Required state |
|---|---|---|
| Lint | `uv run ruff check .` | exit 0 |
| Format | `uv run ruff format --check .` | exit 0 |
| Types (api) | `uv run mypy src tests` | exit 0, strict |
| Tests (api) | `uv run pytest --cov=quid_api --cov-fail-under=85` | exit 0 |
| Types (webui, phases 6+) | `npm --prefix webui run check` | exit 0 |
| E2E (phase 7+) | `npm --prefix webui run test:e2e` | exit 0 |
| Manual smoke (phase 3+) | curl transcript saved | non-empty + 2xx |

If any check fails: fix → re-run → only then commit. **Never** commit a red phase.

---

## 13. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| mypy --strict fights async SQLAlchemy 2.0 | High | Use `Mapped[...]` everywhere, `cast` minimally and only at boundaries, accept `# type: ignore[specific-code]` ONLY with a comment justifying it. Never `as any`-equivalent. |
| pydantic camelCase aliasing breaks PATCH-with-omitted-fields | Medium | Pin model config: `alias_generator=AliasGenerator(serialization_alias=to_camel, validation_alias=to_camel)`, `populate_by_name=True`, `model_dump(by_alias=True, exclude_unset=True)`. Add explicit tests for PATCH-leaves-other-fields-untouched. |
| SQLite FK enforcement off by default | Medium | Connect-event listener issues `PRAGMA foreign_keys=ON`; assert in a dedicated test. |
| Cascade-delete race between UPDATE and DELETE | Low | Both statements in one `async with session.begin()`. |
| Playwright dual-webServer flakes (timing on uvicorn startup) | Medium | Use `webServer.url` healthcheck pointing at `/health` for the api entry, with `timeout: 30_000`. |
| E2E test DB pollution between workers | Medium | One DB file per playwright worker via `PLAYWRIGHT_WORKER_INDEX` in the DB path; reset endpoint operates only on the requesting worker's DB. (Fallback: force `workers: 1` in playwright config until proven otherwise — start with this to reduce risk overnight.) |
| Existing e2e tests have implicit ordering assumptions | Medium | Re-read every test before phase 7; document any that need adjusting; do NOT rewrite test intent, only the state-reset mechanics. |
| Overnight failure leaves repo in broken state | High | Every phase is its own commit; if a phase fails after N attempts, stop, revert to last green commit, write a `.omo/notepads/api/blockers.md` entry, leave summary in final message. |

---

## 14. Out-of-bounds — explicitly will NOT touch

- Existing `webui/src/lib/repos/mock*.ts` files (keep as fallback / dev tool)
- Existing `webui/src/lib/repos/seed.ts` (port logic, don't import it from Python)
- `.omo/plans/expense-tracker-webui.md` (historical)
- Anything outside `api/` and the listed webui files
- `git push`, branch creation, PR creation (commits only on `main`, locally)

---

## 15. Stop conditions

Halt and write a notepad entry instead of pushing through if:

1. Same test fails 3 times after materially different fix attempts
2. mypy --strict requires more than 5 `# type: ignore` comments in a single file (signal of misuse)
3. Phase 7 e2e flakiness can't be stabilised in 30 min of investigation → leave phase 6 committed, mark phase 7 as "blocked: see notes", and write the handoff
4. Any data loss or destructive operation about to run on non-test data
