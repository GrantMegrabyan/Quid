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
| `QUID_CORS_ORIGINS` | `["http://localhost:5173","http://localhost:4173"]` | Allowed webui origins. |
| `QUID_TESTING` | `false` | Mounts `/api/v1/testing/*` helpers when true. |
| `QUID_LOG_LEVEL` | `INFO` | Application log level. |

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
uv run quid-api serve            # run uvicorn on 127.0.0.1:8000
```

## CSV import

The repository includes April 2026 bank exports under `../cvs/`. Start the API first, then import:

```sh
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api migrate
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-dev.db" uv run quid-api serve --port 8000

QUID_API_URL="http://localhost:8000" uv run quid-api import-csv \
  ../cvs/april-2026-grant-monzo.csv \
  ../cvs/april-2026-grant-revolut.csv \
  ../cvs/april-2026-grant-monzo-shared.csv
```

The import endpoint accepts `POST /api/v1/expenses/bulk` with rows shaped as `name`, `category`, `amount`, `date`, and optional `note`. Amounts are stored as positive expense magnitudes and unknown categories are created deterministically, except `other`, which maps to `uncategorized`.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=quid_api --cov-fail-under=85
```
