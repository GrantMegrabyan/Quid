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

The webui reads `PUBLIC_API_BASE_URL` (the browser-reachable API origin) at
**runtime** via SvelteKit's `$env/dynamic/public`; the default is
`http://localhost:8000`. In dev it comes from `.env`; in the Docker image it is
set by the container environment (see _Deployment_), so the same build works in
any environment with no rebuild.

## Deployment

The UI ships as a container built from `Dockerfile` (multi-stage `node:22-alpine`,
using `@sveltejs/adapter-node` → `node build`). Because `PUBLIC_API_BASE_URL` is
read at runtime, the image carries no baked API URL — set it via the
`environment:` block in the repo-root `docker-compose.yml`. See the root README
and `docker-compose.yml` for the full stack (API + UI).

## Pages

- **Dashboard** (`/`) — a single-month spending view headed by the selected
  month and a month selector (with a **Today** button to jump back to the
  current month). Four stat cards: total spent (with a % change vs the previous
  month, fetched from the analytics monthly-totals endpoint), transaction count
  (with the average per transaction), top category (with its share of the
  month), and daily average (for the current month, with a projected month-end
  total once at least 3 days have elapsed). Below them, the cumulative
  spending-trend chart sits beside an always-visible **By category** breakdown —
  a ranked bar list with per-category totals and % shares (top 6, expandable).
  The transaction list has a **search box** (filters by merchant name/display
  name/note, with a match count + total) and a Group-by selector. Each
  transaction's subheading shows the date and, when present, its note (a linked
  Amazon order's short name is used as the note when the expense has none). The
  **selected month** and Group-by choice are remembered across reloads/updates
  in `localStorage`, so the view doesn't snap back to the current month after a
  refresh; it defaults to the current month on first visit.
- **Analytics** (`/analytics`) — insight-first review of your spending, anchored
  on the latest **complete** month (the in-progress month is never the
  headline). Top to bottom:
  - **Verdict header** — "May 2026 — £2,140 · +12% vs your 6-month average",
    with a sparkline of the last 7 complete months and, mid-month, a "June so
    far: £480, on pace for ~£1,950" run-rate line.
  - **AI summary** — an on-demand (never automatic) OpenRouter-generated 3–6
    sentence narrative of the month. The last result is stored server-side and
    shown on revisit with a Regenerate button; a missing
    `QUID_OPENROUTER_API_KEY` surfaces as an inline error.
  - **What went up** — categories above their trailing 6-month average (zero
    months count toward the average), sorted by £ delta. Each row expands to
    the top contributing merchants (vs their own baseline, with "new" badges)
    and the month's transactions. Increases under £10 and 10% roll into one
    "everything else" line; decreases collapse into a "what went down" line.
  - **Where you can save** — price creep on recurring charges (old → new,
    annualised), new recurring charges (first seen in the last 4 months),
    habit spend (≥6 visits at ≤£20 average last month), and the recurring
    stack total (£/mo and £/yr, expandable inventory).
  - **Context** — the monthly trend chart with the 3M/6M/12M/All selector
    (persisted in `localStorage`); the selector only windows this chart —
    the insight zones have fixed windows.

  Empty until transactions are imported. Backed by `GET /api/v1/analytics/*`
  (`summary`, `monthly-totals`, `diagnosis`, `savings`, `narrative`) and
  `POST /api/v1/analytics/narrative`.
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
  chip opens a dropdown; clearing it is allowed). Each order renders as a
  **compact single-line row** (icon link-status indicator, order name, category
  chip, amount, date, then the unlink / find-matches / delete actions) that
  wraps on narrow viewports; an order's full order id is not shown (it carried
  no useful signal). Linked rows expose one **unlink** button per linked
  transaction in the top-line action group (the linked transaction's name +
  amount is in the button tooltip), and find-matches suggestions still appear as
  a secondary panel beneath the row — so linked and unlinked rows share the same
  base height. **Find matches** only ever lists _unlinked_ Amazon charges; when
  it finds none it shows an inline note **at the row** (rather than a banner) —
  worded for context, so an already-linked order reads "Already linked…" instead
  of a misleading "no matches". Action feedback (import results, link/unlink,
  errors) appears as a **dismissible toast pinned to the bottom corner** so it
  stays visible no matter how far you've scrolled. The header's **Re-categorise
  (AI)** button re-runs AI categorisation over all orders against the **current**
  AI rules — useful after editing rules — and opens a preview table: rows whose
  suggestion already matches the current category are hidden behind a **Show
  unchanged** toggle, each changed row is pre-ticked, and **Apply** writes only
  the accepted rows (creating any new categories and updating linked
  transactions). The list is **paginated and filterable** (it only requests one
  page at a time, so it stays fast as your order history grows): a controls bar
  offers a **search** box (matches order id, short name, and item titles), a
  **linked / not-linked** filter, and a **category** filter ("All", "No
  category", or a specific category), with **Previous / Next** page controls and
  a "Showing X–Y of N" count below. Two import paths:
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

## Action feedback & undo

Transient feedback (success / error / undo) is rendered by a single global
**toast host** (`src/lib/components/ToastHost.svelte`, mounted once in the root
layout) and driven by `src/lib/stores/toasts.ts`. Toasts stack in the
bottom-right corner and stay visible regardless of scroll position. Prefer
`notify('success' | 'error', message)` over hand-rolling a per-page banner.

**Deletes are Gmail-style: immediate, with an Undo window — no confirm dialog.**
Every destructive delete in the app (transactions, categories, import rules, AI
rules, Amazon orders) calls `softDelete({ kind, id, message, commit })`:

- The row is hidden immediately (it is added to a global `pendingDeletes` set;
  deletable lists filter that set out), and an **Undo** toast appears with a
  countdown bar.
- **Hovering the Undo toast pauses the countdown** (the progress bar freezes and
  the pending `commit` timer is suspended); moving the mouse away resumes it from
  the remaining time. This gives you as long as you need to decide while the
  pointer is over the toast.
- The real `DELETE` request (`commit`) only runs when the countdown lapses, when
  you dismiss the toast, or when you navigate away / close the tab (a
  `beforeNavigate` + `beforeunload` flush in the layout). Until then nothing has
  been deleted server-side.
- **Undo** cancels before any request is sent — so even the category cascade
  (which reassigns its expenses to Uncategorized) is free to reverse; its
  reassignment count is reported in a follow-up toast only once the delete
  commits. A failed commit re-reveals the row and shows an error toast.

If a full-page reload happens during the undo window, the not-yet-committed
delete is simply skipped and the row reappears — a deliberately safe failure.

## Scripts

```sh
npm run check     # Svelte/TypeScript checks
npm run test:e2e  # builds preview app and runs Playwright against a live test API
npm run build
npm run preview
```

Playwright owns its own SQLite database at `api/.data/quid-e2e.db`, starts the API with `QUID_TESTING=1`, and seeds test state through the testing-only API endpoints. Do not point e2e runs at the dev database.
