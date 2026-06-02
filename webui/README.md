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
  none). The **selected month** (plus the chart toggles and Group-by choice) is
  remembered across reloads/updates in `localStorage`, so the view doesn't snap
  back to the current month after a refresh; it defaults to the current month on
  first visit.
- **Analytics** (`/analytics`) — cross-month spending insights for a selectable
  rolling period (3M / 6M / 12M / All; the choice is remembered across reloads in
  `localStorage`, defaulting to 6M). Shows KPI cards (total spend, average per
  month, transaction count, top category, and a month-over-month delta where an
  **increase is red/up** and a decrease is green/down, since this is spend), a
  monthly-spend line chart, a **Biggest movers** list (the categories that rose
  or fell the most in the latest month with data vs the month before it — labelled
  e.g. "May 2026 vs Apr 2026" — with a signed amount + percent and a "new" badge
  for categories with no prior spend), a multi-series category-trend
  chart (top 8 categories), a spend-by-importance doughnut, a top-merchants bar
  chart, and a spend-by-weekday bar chart. Empty until transactions are imported.
  Backed by the `GET /api/v1/analytics/*` endpoints.
- **Import** (`/import`) — the single place to add transactions, organised into
  three tabs:
  - **CSV file** — the CSV import preview/confirm flow. AI categorisation is no
    longer a per-import checkbox; it follows the **Settings** toggle. Transactions
    that match one already in the app are **not overwritten by default**: a prior
    import may have been intentionally edited, so each matched row is shown
    disabled ("Existing kept") and is skipped on save. Click **Enable to override**
    on a row to apply the imported category/importance to it instead (amount, name,
    date and note are never changed). Matched rows whose category and importance are
    already identical are hidden entirely. Each row also has an **Exclude** toggle
    that drops it from the import — this works for brand-new rows too, not just
    matched ones — and a **Hide/Show N matched** control collapses the existing
    (kept) rows away so you can focus on what's new. The summary bar's
    **excluded** and **invalid** counts are clickable when non-zero: each
    expands a read-only panel listing the affected rows with a per-row reason
    (e.g. _Excluded by AI_, _Detected refund_, or _Amount “abc” is not a
    number_) so you can see exactly which transactions were filtered or dropped
    and why, instead of only a count.
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

  The active tab is remembered across reloads in `localStorage`. A shared
  **Import history** table below the tabs lists every import with a **Source**
  column (CSV vs AI); AI rows can be expanded to show the original pasted text.
- **Amazon orders** (`/amazon`) — import Amazon orders, see which orders are
  linked vs unlinked, link/unlink to transactions, and edit each order's
  AI-generated **short name** and detected **category** inline (the category
  chip opens a dropdown; clearing it is allowed). The header's **Re-categorise
  (AI)** button re-runs AI categorisation over all orders against the **current**
  AI rules — useful after editing rules — and opens a preview table: rows whose
  suggestion already matches the current category are hidden behind a **Show
  unchanged** toggle, each changed row is pre-ticked, and **Apply** writes only
  the accepted rows (creating any new categories and updating linked
  transactions). Two import paths:
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

    #### Adding and running the bookmarklet

    The bookmarklet is a single `javascript:` link generated by quid (it runs
    entirely in your browser — it fetches no remote code and never sends your
    Amazon password or session anywhere). Set it up once, then reuse it.

    **Add it to your browser (one-time):**

    1. In quid, go to **Amazon orders** (`/amazon`) and click **Import from
       browser** to open the panel. You'll see a **"Sync Amazon → quid"** link.
    2. Make sure your **bookmarks bar** is visible
       (Chrome/Edge: `Ctrl`/`Cmd`+`Shift`+`B`; Firefox: View → Toolbars →
       Bookmarks Toolbar; Safari: View → Show Favorites Bar).
    3. **Drag the "Sync Amazon → quid" link onto your bookmarks bar.** That's it.
    4. *If your browser blocks dragging a `javascript:` bookmark* (some do, for
       security): create a bookmark manually instead — right-click the bookmarks
       bar → **Add page / New bookmark**, set the **Name** to `Sync Amazon → quid`,
       and **paste the bookmarklet URL** into the **URL/Location** field. To copy
       the URL: right-click the "Sync Amazon → quid" link → **Copy link address**.
       (Safari often won't let you save a `javascript:` URL via the bar — add it
       from **Bookmarks → Add Bookmark** and edit the address, or use the
       upload/paste flow below with a different browser.)

    **Run it (each time you want to import):**

    1. Open Amazon and sign in, then go to **Returns & Orders** (your order
       history). Choose the time range you want (e.g. a specific year) — the
       bookmarklet scrapes the orders currently shown on the page, so page
       through / select the year(s) you want to capture.
    2. Click the **Sync Amazon → quid** bookmark. It scrapes the visible orders,
       **downloads an `amazon-orders-<domain>-<date>.json` file**, and copies the
       same JSON to your clipboard. An alert confirms how many orders it found.
    3. Back in quid → **Amazon orders** → **Import from browser**, either
       **Upload .json** (pick the downloaded file — the recommended path) or
       **paste** the JSON into the textarea and click **Import pasted JSON**.
    4. quid imports and auto-matches the orders; any it skips (missing total,
       cancelled, unparseable date) are listed with reasons under the banner.
       Re-running the bookmarklet later is safe — re-importing the same orders
       updates them idempotently and never overwrites names/categories you edited.

    **Notes & troubleshooting:**

    - It only scrapes what's **on the page**, so for a full history select each
      year (or use Amazon's "past 3 months" / per-year filters) and run it once
      per view; imports accumulate.
    - Only `amazon.com` / `amazon.co.uk` order pages are tested. Other locales
      may work but aren't guaranteed.
    - If you get a "page layout not recognised" alert, Amazon changed their
      markup — nothing is exported; use **Import CSV** as the fallback and the
      scraper selectors will need updating (`src/lib/amazon/scraper.ts` +
      `src/lib/amazon/bookmarklet.ts`).
    - The bookmarklet's version is shown as `scraperVersion` in the exported
      JSON; it's sourced from `SCRAPER_VERSION` in `scraper.ts` so it can't drift.
- **Settings** (`/settings`) — currency, importance badges, and two AI toggles:
  **AI categorisation** and **AI Amazon short names** (both persisted, default
  on). (Theme switching was removed; the UI uses a single Dasher-style dark
  design on this branch.)
- **Categories** (`/categories`), **Rules** (`/rules`), **AI rules**
  (`/ai-rules`).
  - The **Rules** page can **Preview matches** (dry-run): the add/edit form has a
    Preview button that lists the existing transactions the current draft's
    conditions would match (no save required), and each saved rule card has an
    eye icon that previews that rule's matches. Both call
    `POST /api/v1/import-rules/preview` and never modify data.

## Scripts

```sh
npm run check     # Svelte/TypeScript checks
npm run test:e2e  # builds preview app and runs Playwright against a live test API
npm run build
npm run preview
```

Playwright owns its own SQLite database at `api/.data/quid-e2e.db`, starts the API with `QUID_TESTING=1`, and seeds test state through the testing-only API endpoints. Do not point e2e runs at the dev database.
