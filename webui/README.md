# Expense Tracker Web UI

SvelteKit frontend for Quid. It persists categories and expenses through the FastAPI backend in `../api`.

## Setup

```sh
npm install
cp .env.example .env
```

Start the API first:

```sh
cd ../api
uv sync
uv run quid-api migrate
uv run quid-api serve --reload
```

Then run the web UI:

```sh
npm run dev
```

The webui reads `VITE_API_BASE_URL` from `.env`; the default is `http://localhost:8000`.

## Pages

- **Dashboard** (`/`) — summary stat cards (this month's total with
  month-over-month change, transaction count, the top spending category for the
  month, and average per transaction), plus the transaction list and charts.
  Each transaction's subheading shows the date and, when present, its note (a
  linked Amazon order's short name is used as the note when the expense has
  none).
- **Import** (`/import`) — CSV import preview/confirm. AI categorisation is no
  longer a per-import checkbox; it follows the **Settings** toggle.
- **Amazon orders** (`/amazon`) — import Amazon order CSVs, see which orders are
  linked vs unlinked, link/unlink to transactions, and edit each order's
  AI-generated **short name** and detected **category** inline (the category
  chip opens a dropdown; clearing it is allowed).
- **Settings** (`/settings`) — currency, importance badges, and two AI toggles:
  **AI categorisation** and **AI Amazon short names** (both persisted, default
  on). (Theme switching was removed; the UI uses a single Dasher-style dark
  design on this branch.)
- **Categories** (`/categories`), **Rules** (`/rules`), **AI rules**
  (`/ai-rules`).

## Scripts

```sh
npm run check     # Svelte/TypeScript checks
npm run test:e2e  # builds preview app and runs Playwright against a live test API
npm run build
npm run preview
```

Playwright owns its own SQLite database at `api/.data/quid-e2e.db`, starts the API with `QUID_TESTING=1`, and seeds test state through the testing-only API endpoints. Do not point e2e runs at the dev database.
