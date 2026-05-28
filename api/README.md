# Quid API

FastAPI + SQLite backend for the Quid expense tracker. Python tooling is managed with `uv`.

## Quickstart

```sh
uv sync
uv run quid-api migrate
uv run quid-api seed --reset
uv run quid-api serve --reload
```

The API listens on `http://localhost:8000` by default. OpenAPI docs are available at `http://localhost:8000/docs`.

## Configuration

Environment variables use the `QUID_` prefix and can also be placed in `api/.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `QUID_DATABASE_URL` | `sqlite+aiosqlite:///./.data/quid.db` | Async SQLAlchemy database URL. |
| `QUID_CORS_ORIGIN_REGEX` | `^http://localhost(:\d+)?$` | Allowed browser origins. Defaults to any `http://localhost` port. |
| `QUID_TESTING` | `false` | Mounts `/api/v1/testing/*` helpers when true. |
| `QUID_LOG_LEVEL` | `INFO` | Application log level. |
| `QUID_OPENROUTER_API_KEY` | unset | OpenRouter API key for the AI features (CSV import categorisation and Amazon order short names). Required when either AI feature is enabled. |
| `QUID_OPENROUTER_MODEL` | `openai/gpt-5.4-mini` | OpenRouter model used for both AI categorisation and Amazon short names. |
| `QUID_OPENROUTER_CHUNK_SIZE` | `25` | Max items per OpenRouter call. Larger imports are split into sequential chunks; for categorisation each chunk's prompt carries forward the merchant→category decisions made by earlier chunks. Set lower if the model struggles on long batches; raise (or set to a very large number) to revert to single-shot behaviour. |

Whether the two AI features actually run is controlled by persisted **app
settings** (not env vars): `aiCategorizeEnabled` and `aiShortNamesEnabled`
(both default true). Edit them on the web UI **Settings** page or via
`PATCH /api/v1/settings`. The env vars above only supply credentials/model.

Example dev database:

```sh
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api migrate
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api serve --reload
```

## CLI

```sh
uv run quid-api migrate          # upgrade SQLite schema to head
uv run quid-api migrate --down 1 # downgrade one Alembic revision
uv run quid-api seed --reset     # reset to deterministic sample data
uv run quid-api clear-transactions # delete expenses and import logs
uv run quid-api serve            # run uvicorn on 127.0.0.1:8000
uv run quid-api backfill-amazon-short-names # AI-name imported Amazon orders missing one
```

`backfill-amazon-short-names` generates and stores a short name for every
Amazon order that does not already have one (it never overwrites existing or
user-edited names, so it is safe to re-run). It calls OpenRouter, so it needs
`QUID_OPENROUTER_API_KEY`.

## CSV import

Two transports import CSVs:

1. **HTTP, multipart** — `POST /api/v1/expenses/import-csv` accepts one or many `files` parts. This is what the web UI uses (dashboard → **Import CSV**).
2. **CLI shim** — `uv run quid-api import-csv` posts JSON rows to `/api/v1/expenses/bulk`.

```sh
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api migrate
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api serve --port 8000

# Multipart, idempotent, multiple files in one request:
curl -X POST http://localhost:8000/api/v1/expenses/import-csv \
  -F "files=@../samples/april-2026-grant-monzo-shared.csv" \
  -F "files=@../samples/april-2026-grant-revolut.csv"
```

AI categorisation of parsed transactions runs automatically when the
`aiCategorizeEnabled` app setting is true (the default; toggle it on the
Settings page or via `PATCH /api/v1/settings`). There is **no** `ai_categorize`
form field — passing one returns HTTP 422. When AI categorisation is enabled the
API requires `QUID_OPENROUTER_API_KEY`.

### Accepted column shapes

The CSV parser matches headers case-insensitively and tolerates extra columns.
Required logical fields: `name`, `amount`, `date`. Optional: `category`, `note`.

| Logical field | Accepted header aliases |
| --- | --- |
| name | `name`, `description`, `merchant`, `payee` |
| amount | `amount`, `value` |
| date | `date`, `completed date`, `started date`, `transaction date`, `posting date` |
| category | `category`, `type`, `tag` (defaults to `uncategorized`) |
| note | `note`, `notes`, `memo`, `reference` |

Amounts are stored as positive expense magnitudes (negatives are abs'd). Dates accept `YYYY-MM-DD` and `YYYY-MM-DD HH:MM:SS` (the time portion is dropped). If a `state` / `status` column is present, only `COMPLETED` rows are kept (Revolut bank-statement convention).

### Idempotency

The endpoint deduplicates by the tuple `(date, lower(trim(name)), amount, lower(trim(note)))`.
Category is intentionally excluded from the key: AI categorisation is non-deterministic
across runs, import-rule sets change over time, and users re-categorise rows by hand —
including category in the key let identical transactions slip through whenever the
category drifted between imports.

For each unique normalised tuple, the server inserts
`max(0, rows_in_file − rows_already_in_db)`, so re-uploading the same file is a no-op
while several legitimate identical transactions in the **same** file (e.g. two parking
charges to the same merchant for the same amount on the same day) still accumulate.

The response reports `imported`, `skippedDuplicates`, `skippedInvalidRows`,
`skippedExcluded`, and a per-file breakdown.

## Amazon orders

Amazon order exports are imported and linked to transactions so the UI can show
what an Amazon charge actually bought.

- `POST /api/v1/amazon-orders/import-csv` — multipart `files`. Parses orders,
  upserts them (re-importing an order id replaces its details idempotently),
  and runs auto-matching against unlinked expenses.
- `GET /api/v1/amazon-orders` / `GET /api/v1/amazon-orders/{id}` — list / fetch.
- `POST /api/v1/amazon-orders/match-all` — re-run auto-matching.
- `GET /api/v1/amazon-orders/{id}/suggested-matches` — candidate expenses.
- `POST /api/v1/amazon-orders/{id}/link` / `/unlink` — body `{ "expenseId": "…" }`.
  An expense ↔ order link is many-to-many (`expense_amazon_orders` table).
- `PATCH /api/v1/amazon-orders/{id}/short-name` — body `{ "shortName": "…" }`
  (≤60 chars). Sets a user-edited short name.
- `DELETE /api/v1/amazon-orders/{id}`.

Each order has a **short name**: a brief (≤60 char) AI description of what was
purchased. It is generated once at import time (only when `aiShortNamesEnabled`
is true) and stored; re-importing the same order never overwrites it, and when
AI short names are disabled the field is left blank. A linked order's short name
is surfaced as the transaction's note in the expense list when the expense has
no note of its own. Backfill missing names with
`uv run quid-api backfill-amazon-short-names`.

## Settings

`GET /api/v1/settings` returns the app-settings singleton; `PATCH /api/v1/settings`
updates it. Fields (camelCase): `currency`, `showImportanceBadge`,
`aiCategorizeEnabled`, `aiShortNamesEnabled`. The two `ai*Enabled` flags gate the
AI features described above and both default to true. These are edited from the
web UI **Settings** page.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=quid_api --cov-fail-under=85
```
