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
| `QUID_OPENROUTER_API_KEY` | unset | OpenRouter API key for optional AI categorisation during CSV import. |
| `QUID_OPENROUTER_MODEL` | `openai/gpt-5.4-mini` | OpenRouter model used for CSV import categorisation. |

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
uv run quid-api clear-transactions # delete expenses and orphaned categories
uv run quid-api serve            # run uvicorn on 127.0.0.1:8000
```

## CSV import

Two transports import CSVs:

1. **HTTP, multipart** — `POST /api/v1/expenses/import-csv` accepts one or many `files` parts. This is what the web UI uses (dashboard → **Import CSV**).
2. **CLI shim** — `uv run quid-api import-csv` posts JSON rows to `/api/v1/expenses/bulk`.

```sh
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api migrate
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api serve --port 8000

# Multipart, idempotent, multiple files in one request:
curl -X POST http://localhost:8000/api/v1/expenses/import-csv \
  -F "ai_categorize=false" \
  -F "files=@../samples/april-2026-grant-monzo-shared.csv" \
  -F "files=@../samples/april-2026-grant-revolut.csv"
```

Set `ai_categorize=true` to categorise parsed transactions with OpenRouter before saving.
When enabled, the API requires `QUID_OPENROUTER_API_KEY`.

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

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=quid_api --cov-fail-under=85
```
