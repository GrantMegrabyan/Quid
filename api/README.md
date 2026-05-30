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
| `QUID_CORS_ORIGIN_REGEX` | `^http://localhost(:\d+)?$` | Allowed browser origins **in development**. Defaults to any `http://localhost` port. Ignored in production (use `QUID_CORS_ALLOWED_ORIGINS`). |
| `QUID_TESTING` | `false` | Mounts the **destructive** `/api/v1/testing/*` helpers when true (see _Testing endpoints_ below). Must be `false` in production. |
| `QUID_TESTING_TOKEN` | empty | Shared secret required on **every** `/api/v1/testing/*` request via the `X-Testing-Token` header. When `QUID_TESTING=true` but this is empty the router is mounted yet **rejects all requests** (`403`). A wrong/missing header returns `401`. |
| `QUID_TESTING_ALLOW_UNSAFE_DB` | `false` | Override the startup guard that refuses to boot when `QUID_TESTING=true` and `QUID_DATABASE_URL` does not look like a throwaway test/e2e DB (must contain `test`, `e2e`, or `:memory:`). Leave `false` so the data-wiping router can never be pointed at a real DB by accident. |
| `QUID_ENVIRONMENT` | `development` | Deployment mode. Set to `production` to enable fail-fast safety checks and lock down docs/CORS/hosts (see _Production hardening_). |
| `QUID_ALLOWED_HOSTS` | empty | Comma-separated list of trusted `Host` header values, enforced by `TrustedHostMiddleware`. Empty means "any host" (fine for local dev; **required** and must not contain `*` in production). |
| `QUID_CORS_ALLOWED_ORIGINS` | empty | Comma-separated list of exact allowed browser origins used **in production** (e.g. `https://app.example.com`). **Required** and must not contain `*` in production; ignored in development. |
| `QUID_DOCS_ENABLED` | `false` | Whether to expose `/docs`, `/redoc` and `/openapi.json`. Docs are **always on in development** regardless of this flag; in production they are **off** unless this is `true`. |
| `QUID_SECURITY_HEADERS_ENABLED` | `true` | Attach safe static response headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`) to every response. |
| `QUID_LOG_LEVEL` | `INFO` | Application log level. |
| `QUID_OPENROUTER_API_KEY` | unset | OpenRouter API key for the AI features (CSV import categorisation, Amazon order categorisation, and Amazon order short names). Required when an AI feature is enabled. |
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

## Production hardening

The API ships in **development mode** by default, which keeps the permissive
localhost behaviour: CORS allows any `http://localhost` port, any `Host` header
is accepted, and `/docs` + `/openapi.json` are served. Nothing below changes
local development.

Setting `QUID_ENVIRONMENT=production` turns on production hardening:

- **Fail-fast config validation.** The app refuses to start (raises
  `ProductionConfigError`) when `QUID_ALLOWED_HOSTS` or
  `QUID_CORS_ALLOWED_ORIGINS` is missing or contains `*`, or when
  `QUID_TESTING` is true. This prevents accidentally deploying with a wildcard
  CORS/host configuration.
- **Locked-down CORS.** The development `QUID_CORS_ORIGIN_REGEX` is ignored;
  only the exact origins in `QUID_CORS_ALLOWED_ORIGINS` are allowed.
- **`TrustedHostMiddleware`.** Requests whose `Host` header is not in
  `QUID_ALLOWED_HOSTS` get a `400 Bad Request`. (This middleware is also added
  in development if you choose to set `QUID_ALLOWED_HOSTS` there.)
- **Docs disabled.** `/docs`, `/redoc` and `/openapi.json` return `404` unless
  you explicitly set `QUID_DOCS_ENABLED=true`.

Security response headers (`X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Cross-Origin-Opener-Policy`) are attached in **both** modes
(toggle with `QUID_SECURITY_HEADERS_ENABLED`). HSTS is intentionally not set
here — terminate TLS and set `Strict-Transport-Security` at your reverse proxy.

Database integrity errors (unique / foreign-key / check / not-null violations)
are sanitized into the normal API error shape instead of bubbling up as HTTP
500s with raw SQL/driver text.

### Local (development) — unchanged

```sh
uv run quid-api migrate
uv run quid-api serve --reload
# CORS: any http://localhost:* ; any Host accepted ; /docs available
```

### Production

```sh
QUID_ENVIRONMENT=production \
QUID_ALLOWED_HOSTS="api.example.com" \
QUID_CORS_ALLOWED_ORIGINS="https://app.example.com" \
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid.db" \
  uv run quid-api serve --host 0.0.0.0 --port 8000

# To expose the API docs in production as well, add:
#   QUID_DOCS_ENABLED=true
```

Multiple hosts/origins are comma-separated, e.g.
`QUID_CORS_ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"`.

## Testing endpoints

> [!WARNING]
> The `/api/v1/testing/*` router is **destructive**. `POST /api/v1/testing/reset`
> and `POST /api/v1/testing/seed-state` **delete every expense and every
> category** (except the built-in `Uncategorized`) before optionally seeding
> sample/given data. It exists only so the e2e harness can reset state between
> tests. **Never enable it against a database whose data you care about.**

These endpoints are guarded three ways so they cannot be triggered by accident:

1. **Not mounted by default.** They only exist when `QUID_TESTING=true`. With the
   default (`false`) the routes return `404`.
2. **Token required.** Even when mounted, every request must send the
   `X-Testing-Token` header matching `QUID_TESTING_TOKEN`. A missing/incorrect
   token returns `401`; if `QUID_TESTING_TOKEN` is unset the router rejects
   everything with `403` (fail-closed — mounting alone is not enough).
3. **Database-safety startup guard.** When `QUID_TESTING=true` the app **refuses
   to start** (`TestingConfigError`) if `QUID_DATABASE_URL` does not look like a
   throwaway test database (it must contain `test`, `e2e`, or `:memory:`). Set
   `QUID_TESTING_ALLOW_UNSAFE_DB=true` only if you deliberately need to bypass
   this. In production, `QUID_TESTING=true` is rejected outright by the
   production hardening checks above.

The Playwright e2e harness boots its own API with
`QUID_TESTING=1`, `QUID_TESTING_TOKEN` set, and `QUID_DATABASE_URL` pointing at
`api/.data/quid-e2e.db`; the test helpers send the matching `X-Testing-Token`
header on every reset/seed call.

Example (local, throwaway DB):

```sh
QUID_TESTING=1 \
QUID_TESTING_TOKEN="dev-testing-token" \
QUID_DATABASE_URL="sqlite+aiosqlite:///./.data/quid-test.db" \
  uv run quid-api serve --port 8001

# Reset (wipes data) — requires the token:
curl -X POST http://localhost:8001/api/v1/testing/reset \
  -H "X-Testing-Token: dev-testing-token"
```

## CLI

```sh
uv run quid-api migrate          # upgrade SQLite schema to head
uv run quid-api migrate --down 1 # downgrade one Alembic revision
uv run quid-api seed --reset     # reset to deterministic sample data
uv run quid-api clear-transactions # delete expenses and import logs
uv run quid-api serve            # run uvicorn on 127.0.0.1:8000
uv run quid-api backfill-amazon-short-names # AI-name imported Amazon orders missing one
uv run quid-api backfill-amazon-categories  # AI-categorise imported Amazon orders missing one
```

`backfill-amazon-short-names` generates and stores a short name for every
Amazon order that does not already have one (it never overwrites existing or
user-edited names, so it is safe to re-run). It calls OpenRouter, so it needs
`QUID_OPENROUTER_API_KEY`.

`backfill-amazon-categories` AI-categorises every Amazon order that does not
already have a category, then propagates that category to any already-linked
uncategorised expense. It never overwrites an order's existing category or a
non-uncategorised expense category, so it is safe to re-run. It calls
OpenRouter, so it needs `QUID_OPENROUTER_API_KEY`.

## Adding transactions

The web UI's **Import** page is the single place to add transactions. It offers
three modes, all of which ultimately write through the endpoints below:

1. **CSV file** — preview/review/confirm a bank export (see below).
2. **Single transaction** — a plain form that `POST`s one expense to
   `/api/v1/expenses` (no AI; the user picks the category).
3. **AI free-form** — paste free-form text; an AI extracts transactions which are
   then reviewed/confirmed exactly like a CSV import (see _AI free-form import_).

A single expense is created with `POST /api/v1/expenses` (JSON body matching
`ExpenseCreate`: `name`, `amount`, `date`, `categoryId`, `note?`, `importance?`).

## CSV import

Two transports import CSVs:

1. **HTTP, multipart** — `POST /api/v1/expenses/import-csv` accepts one or many `files` parts. This is what the web UI's Import page uses (**Import → CSV file**).
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

The endpoint deduplicates by the tuple `(date, lower(trim(name)), amount)`.
Neither category nor note is part of the key. AI categorisation is non-deterministic
across runs, import-rule sets change over time, and users re-categorise rows by hand;
note is likewise incidental and user-mutable (manual edits, or a differing export from
the bank). Including either let identical transactions slip through whenever the value
drifted between imports — same merchant, same day, same amount is the same transaction
regardless of category or note.

For each unique normalised tuple, the server inserts
`max(0, rows_in_file − rows_already_in_db)`, so re-uploading the same file is a no-op
while several legitimate identical transactions in the **same** file (e.g. two parking
charges to the same merchant for the same amount on the same day) still accumulate.

The response reports `imported`, `skippedDuplicates`, `skippedInvalidRows`,
`skippedExcluded`, and a per-file breakdown.

### Preview / confirm

The Import page never writes straight from a file. It first calls
`POST /api/v1/expenses/import-csv/preview` (multipart `files`) to get a reviewable
plan (creates, category updates for existing rows, hidden duplicates, excluded
rows), then `POST /api/v1/expenses/import-csv/confirm` with the reviewed rows to
persist. Confirm records an import-log entry (see _Import history_).

**Matched (existing) transactions are not updated by default.** A row that
matches an existing expense by `(date, lower(trim(name)), amount)` but carries a
different category/importance comes back as `kind = "category_update"`. The
confirm payload carries one `categoryUpdates` entry per such row with an `accept`
flag; the server only overwrites the existing expense's category/importance when
`accept` is `true` (and only those two fields — amount/name/date/note define the
match and are never touched). The web UI sends `accept = false` by default and
flips it to `true` only when the user clicks **Enable to override** on the row,
so a re-import never silently clobbers fields the user intentionally edited on a
previous import. Rows that match with an identical category **and** importance
are hidden as `duplicate_same_category` and never sent to confirm.

## AI free-form import

Lets a user paste free-form text (e.g. `coffee 3.50 yesterday, Tesco 42 on the
3rd`) and have an AI turn it into transactions. It mirrors the CSV
preview/confirm flow so the same review UI is reused.

- `POST /api/v1/expenses/import-freeform/preview` — JSON body `{ "rawInput": "…" }`
  (1–10 000 chars). The text is parsed by OpenRouter into rows, then run through
  the same AI categorisation (when `aiCategorizeEnabled`) and preview pipeline as
  CSV. Returns the same `ImportCsvPreviewResponse` shape (rows use the synthetic
  filename `AI free-form`). Requires `QUID_OPENROUTER_API_KEY`.
- `POST /api/v1/expenses/import-freeform/confirm` — JSON body `{ "importId",
  "rawInput", "creates": [...], "categoryUpdates": [...] }` (same reviewed-row
  shapes as CSV confirm). The `amount` on each create row is whatever the user
  reviewed/edited in the UI (it is not forced back to the AI-parsed value), so a
  corrected amount is persisted. Persists the rows and records an import-log entry
  with `source = "freeform"` and the `rawInput` preserved. Idempotent: confirm
  re-runs the bulk dedup against the DB by `(date, name, amount)` at write
  time, so re-confirming identical rows creates nothing (`skippedDuplicates`),
  while an edited amount counts as a distinct transaction.

## Import history

`GET /api/v1/import-logs` returns recent import batches (CSV and free-form),
newest first. Each entry (`ImportLogOut`, camelCase) has: `id`, `importedAt`,
`source` (`"csv"` | `"freeform"`), `files` (list; empty for free-form),
`rawInput` (the submitted text for `freeform`, else `null`), `imported`,
`updated`, `skippedDuplicates`, `skippedExcluded`, `skippedInvalidRows`. The web
UI shows this as the **Import history** table below the Import tabs, with a
**Source** column and an expandable raw-input view for AI free-form runs.

## Amazon orders

Amazon order exports are imported and linked to transactions so the UI can show
what an Amazon charge actually bought.

- `POST /api/v1/amazon-orders/import-csv` — multipart `files`. Parses orders,
  upserts them (re-importing an order id replaces its details idempotently),
  AI-categorises new orders (when `aiCategorizeEnabled`), and runs auto-matching
  against unlinked expenses.
- `POST /api/v1/amazon-orders/import-export` — JSON body, for orders scraped by
  the webui browser bookmarklet (see `webui/README.md`). Feeds the SAME
  ingest/upsert/AI/match pipeline as CSV (`source="export"` provenance, logged
  only). CSV import remains fully supported as the canonical fallback.

  **Money-as-strings contract:** every monetary field (order `total`, item
  `price`, shipment `total`) MUST be a JSON **string** (`"19.99"`), never a JSON
  number. The matcher does exact `Decimal` equality, so a JSON number produced
  by the scraper's float arithmetic would silently fail to match. Typing money
  as a string makes a number a hard 422.

  Request body (camelCase):

  ```json
  {
    "scraperVersion": "1.0.0",
    "domain": "amazon.co.uk",
    "orders": [
      {
        "orderId": "111-2223334-4445556",
        "orderDate": "2026-05-05",
        "total": "19.99",
        "currency": "GBP",
        "status": "Delivered",
        "items": [{ "title": "USB-C Cable 2m", "quantity": 1, "price": "19.99" }],
        "shipments": [],
        "paymentLast4": "1234",
        "orderUrl": "https://www.amazon.co.uk/gp/css/order-details?orderID=111-2223334-4445556"
      }
    ]
  }
  ```

  Validation mirrors the CSV path: **structural** problems are 422s (body not an
  object, `orders` missing/not an array/empty), while **row-level** problems are
  SKIPPED per-order with a reason (blank `orderId`, non-importable `status`,
  unparseable `orderDate`, missing/non-positive `total`) so a partial scrape
  still imports its good orders. Response is the shared `AmazonImportResult`,
  with the single synthetic file report carrying the skips:

  ```json
  {
    "created": 1,
    "updated": 0,
    "autoMatched": 1,
    "ambiguous": 0,
    "combinedMatched": 0,
    "files": [
      {
        "filename": "amazon.co.uk",
        "ordersParsed": 1,
        "skippedRows": 1,
        "skipped": [{ "orderId": "903-…", "reason": "Order total is missing or not a positive amount." }]
      }
    ]
  }
  ```

  The `skipped[]` per-order reasons are populated by this endpoint only; the CSV
  importer leaves it empty (it tracks only the aggregate `skippedRows`).
- `GET /api/v1/amazon-orders` / `GET /api/v1/amazon-orders/{id}` — list / fetch.
  Each order includes `categoryId` (the order's AI-derived category, or `null`).
- `POST /api/v1/amazon-orders/match-all` — re-run auto-matching.
- `GET /api/v1/amazon-orders/{id}/suggested-matches` — candidate expenses.
- `POST /api/v1/amazon-orders/{id}/link` / `/unlink` — body `{ "expenseId": "…" }`.
  An expense ↔ order link is many-to-many (`expense_amazon_orders` table).
- `PATCH /api/v1/amazon-orders/{id}/short-name` — body `{ "shortName": "…" }`
  (≤60 chars). Sets a user-edited short name.
- `PATCH /api/v1/amazon-orders/{id}/category` — body `{ "categoryId": "…" | null }`.
  Sets (or clears, with `null`) the order's category. A non-null id must exist
  (else 422). Setting it pushes the category onto linked `ai`/`import` expenses
  (same override rules as inheritance); `null` only clears the order's own
  category. The webui Amazon page shows each order's category as an editable
  chip.
- `DELETE /api/v1/amazon-orders/{id}`.

Each order has a **short name**: a brief (≤60 char) AI description of what was
purchased. It is generated once at import time (only when `aiShortNamesEnabled`
is true) and stored; re-importing the same order never overwrites it, and when
AI short names are disabled the field is left blank. A linked order's short name
is surfaced as the transaction's note in the expense list when the expense has
no note of its own. Backfill missing names with
`uv run quid-api backfill-amazon-short-names`.

Each order also has a **category** (`categoryId`): an AI-derived spending
category chosen from the same category set as expenses, using the order's item
titles. It is generated once at import time (only when `aiCategorizeEnabled` is
true) and stored; re-importing never overwrites a non-null category. Backfill
missing categories with `uv run quid-api backfill-amazon-categories`.

**Category inheritance & precision.** Each expense records a
`categorySource` (read-only on `ExpenseOut`) marking where its category came
from, with priority high→low: `manual` > `rule` > `amazon` > `ai` > `import`.
When an order is linked to an expense (auto-match or manual link), the expense
inherits the order's (precise, item-derived) category **only when its current
source is `ai` or `import`** — i.e. a generic expense-AI guess (the typical
Amazon "Shopping") or an unset/import default. A category set by the user
(`manual`), an import rule (`rule`), or a previous order (`amazon`) is never
overwritten. This is the precision fix: per-order categories replace the coarse
"Shopping" bucket but protect deliberate choices.

`categorySource` is set per write path: manual create / edit / accepted import
suggestion → `manual`; import-rule match → `rule`; expense-import AI → `ai`;
bulk/default import → `import`; Amazon inheritance → `amazon`. Deleting a
category resets affected expenses to `uncategorized`/`import` (re-categorisable).

For a combined charge (2–3 orders → one expense), the expense inherits a
category only when all participating orders agree on it. Unlinking does not
revert an inherited category.

The `backfill-amazon-categories` command, after categorising orders, runs a
standalone pass that pushes every categorised order's category onto its linked
`ai`/`import` expenses — so already-imported "Shopping" Amazon expenses get the
precise category even though their orders were linked before this feature
existed.

**Matching is restricted to Amazon merchants:** auto-matching and
`suggested-matches` only consider expenses whose name looks like an Amazon
charge (matches `amazon` / `amzn` / `amz`). Manual `/link` is unrestricted, so
you can still link any expense by id.

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
