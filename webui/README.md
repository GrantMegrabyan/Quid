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
- **Import** (`/import`) — the single place to add transactions, organised into
  three tabs:
  - **CSV file** — the CSV import preview/confirm flow. AI categorisation is no
    longer a per-import checkbox; it follows the **Settings** toggle.
  - **Single transaction** — an inline form (merchant, amount, date, category,
    importance, note) for adding one transaction at a time.
  - **AI free-form** — paste plain-English lines (e.g. `coffee 3.50 yesterday`)
    and let AI parse them into a preview you review (amount/category/importance)
    before confirming. The **amount** on each new row is editable in the review
    table, so you can correct what the AI parsed; the edited amount is what gets
    saved. Confirming is idempotent — re-confirming the same transactions does not
    re-import them (dedup is by date/name/amount/note at save time, so changing the
    amount makes it a genuinely new transaction). Backed by
    `POST /api/v1/expenses/import-freeform/{preview,confirm}`.

  A shared **Import history** table below the tabs lists every import with a
  **Source** column (CSV vs AI); AI rows can be expanded to show the original
  pasted text.
- **Amazon orders** (`/amazon`) — import Amazon orders, see which orders are
  linked vs unlinked, link/unlink to transactions, and edit each order's
  AI-generated **short name** and detected **category** inline (the category
  chip opens a dropdown; clearing it is allowed). Two import paths:
  - **Import CSV** — upload one or more Amazon order-export CSVs (the canonical,
    reliable path).
  - **Import from browser** — for when you don't want to hunt for a CSV. Opens a
    panel with a **bookmarklet** ("Sync Amazon → quid") to drag onto your
    bookmarks bar. On your Amazon orders page (Returns & Orders), click the
    bookmark: it scrapes the visible orders **in your own logged-in browser**
    (no Amazon password or session ever reaches quid), downloads a `.json` file,
    and copies the JSON to your clipboard. Back in quid, **upload the `.json`**
    (primary) or **paste the JSON** into the textarea and submit. Orders feed the
    same ingest/match pipeline as CSV. Any orders the server drops (missing
    total, cancelled, bad date) are listed with reasons below the banner.

    The scraper is **fail-loud**: if Amazon's page layout has drifted beyond
    recognition it aborts with an explanatory alert and exports nothing, so you
    never import truncated/garbage data — fall back to the CSV import. The
    parser lives in `src/lib/amazon/scraper.ts` (canonical, fixture-tested via
    `tests/amazon-scraper.e2e.ts`); the bookmarklet in
    `src/lib/amazon/bookmarklet.ts` is a self-contained derivative that must be
    kept in sync with it.
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
