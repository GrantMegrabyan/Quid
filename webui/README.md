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

- **Dashboard** (`/`) — the spending view for a **window** (see "The window"
  below): a single month, or a rolling period. It is headed by the window's
  total, the % change against the comparable previous window, and the window
  control (month stepper + `3M / 6M / YTD / 1Y / ALL`). A ruled strip carries
  the transaction count (with the average per transaction), the daily average
  (with a projected month-end total when a month is still in progress and at
  least 3 days have elapsed), and the top category with its share.
  Below that, a two-column layout: the main column holds the **Spending** chart
  (cumulative by day for a month, a bar per month for a period — the in-progress
  month is drawn hollow) and **Where it went**, a ranked category bar list (top
  6, expandable) coloured by RANK from the theme's series palette rather than by
  each category's own hex. The right rail holds three read-only cards —
  **Needs review** (uncategorised count + how many rows were categorised
  automatically, each of which applies the matching filter below),
  **Top merchants**, and **Essential vs discretionary**.
  The transaction list is a **register** under a **filter bar**: search
  (merchant/display name/note), a **Category** faceted multi-select showing each
  category's row count, an amount band (min/max), a review-status filter
  (All / Uncategorised / Auto-categorised), and the Group-by selector, with a
  running "Showing N of M" count and **Clear filters**. On desktop, flat view
  buckets rows under per-day headers with a daily subtotal, and each row spreads
  into aligned columns (icon, merchant, category pill, note, amount,
  hover-revealed edit/delete). Grouped views (merchant/category/importance)
  render each group header with a proportional share bar + % of the window, and
  expand into child rows using the same columns. On mobile, rows fall back to a
  compact stacked layout.
  In flat view each row's category tile doubles as its **checkbox** (it flips on
  hover, and stays flipped while anything is selected); selecting rows raises a
  **bulk bar** that can recategorise the selection in one go (PATCHing each row,
  which marks its category source `manual`) or delete it through the usual
  undo-able soft delete. The selection is dropped automatically when a row
  leaves the current filter, so a bulk action can never hit an invisible row.
  A transaction's note is the expense's own note or, for a linked Amazon order
  without one, the order's short name. The window and the Group-by choice are
  remembered across reloads in `localStorage`.
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
- **Importance** (`/importance`) — the triage queue. Every transaction carries
  an importance (Essential / Important / Discretionary), but until you set one
  by hand it is only a guess, and the stored value cannot be told apart from the
  untouched default. This page lists the merchants that have **no** hand-set
  importance yet, ranked by total spend, so the biggest decisions come first:
  labelling the top handful usually covers most of the money.
  - Each row shows the merchant, its category, total spend, transaction count,
    and what those rows currently hold; the three buttons label the whole
    merchant in one click.
  - Labelling applies **retroactively** to that merchant's existing
    transactions, but never overwrites a transaction whose importance you set
    individually — a per-transaction decision is more specific.
  - Merchants are matched case-insensitively (`Tesco` and `TESCO` are one row).
  - The header strip tracks how much spend is labelled, how many merchants are
    done, and how often your decisions changed what quid proposed.
  - Every decision here (and every importance you change on a transaction or in
    an import preview) is recorded server-side as a correction, which is the
    training data a future automatic pass will learn from.
- **Settings** (`/settings`) — currency, importance badges, and two AI toggles:
  **AI categorisation** and **AI Amazon short names** (both persisted, default
  on), plus **Appearance** (Paper / Ink / System). Appearance is a *device*
  preference: it applies immediately, is stored in `localStorage`, and is not
  part of the saved app settings (so it never round-trips to the API).
- **Categories** (`/categories`), **Rules** (`/rules`), **AI rules**
  (`/ai-rules`).
  - A `categorize` rule can rewrite three things on every row it matches:
    **Set display name**, **Set note** and **Set importance**
    (Essential / Important / Discretionary, defaulting to "Leave as imported").
    All three are hidden for `exclude` rules, since those delete the row. A
    rule's importance beats the AI's and the CSV's guess, and each rule card
    spells its effects out ("Then categorize as Housing, mark essential").
  - The **Rules** page can **Preview matches** (dry-run): the add/edit form has a
    Preview button that lists the existing transactions the current draft's
    conditions would match (no save required), and each saved rule card has an
    eye icon that previews that rule's matches. Both call
    `POST /api/v1/import-rules/preview` and never modify data.

## The window

Every number on the dashboard describes one **window**, and the window is a
selection, not a date:

```ts
type PeriodSelection =
  | { kind: 'month';  monthKey: string; restoreCode: PeriodCode }  // steppable
  | { kind: 'period'; code: '3M' | '6M' | 'YTD' | '1Y' | 'ALL' };  // ends today
```

- **Resolution** lives in `src/lib/utils/period.ts` (`resolvePeriod`): it turns a
  selection into `{ from, to, prior, label, priorLabel, granularity, inProgress }`.
  The **comparison window** follows what a person would draw by hand — a month
  compares with the previous calendar month; a rolling period compares with the
  equally long window ending the day before it starts; `ALL` has no comparison.
  The prior window's total is fetched as ONE aggregate
  (`/api/v1/analytics/summary?date_from&date_to`), never as a second page of rows.
- **State** lives in `src/lib/stores/ui.ts`: `selection` (persisted under
  `quid:period:v2`; the old `quid:selected-month:v1` key is no longer read),
  plus the derived `resolvedPeriod`, `selectedMonth` and `isMonthMode`, and the
  writers `setPeriod` / `setMonth` / `stepMonth` / `goCurrentMonth`. Write through
  those — `selectedMonth` is read-only now.
- **Month mode is first-class**, and is the default. Stepping the month leaves
  period mode (remembering the code to restore), and picking a code leaves month
  mode. Analytics that only make sense for a calendar month (the cumulative
  chart, the month-end projection) are gated on `isMonthMode`.
- **The URL is the shareable form**: `?month=2026-07` or `?period=6M`. On load the
  URL wins over the persisted selection; afterwards the selection writes back
  with `replaceState`.
- **`ALL` fetches from an epoch sentinel** (`1970-01-01`), which is a *fetch*
  bound and not a real window start. Anything DISPLAYING the window must read
  `viewWindow` (`src/lib/stores/window.ts`) instead of `resolvedPeriod`: it
  narrows an all-time window to the earliest transaction actually loaded, via
  `clampToData` in `period.ts`. Charting the raw bound drew a bar for every
  month since 1970 and divided the daily average by ~20,000 days. Only `ALL` is
  clamped — a chosen window keeps its empty months, since a gap inside "last 6
  months" is a real finding. `viewWindow` lives in its own store because
  `resolvedPeriod` must NOT depend on the loaded rows (the fetch is keyed off
  it and would chase its own tail), and because `expenses.ts` already imports
  `ui.ts`.
- **The store is the window.** `refreshExpenses()` fetches exactly the resolved
  range in one request, so `$expenses` holds the window and nothing else.
  Components must NOT re-filter by date — that was the old month-scoped contract
  and it is gone. Anything needing a row from outside the window (e.g. an Amazon
  order's linked charge of any date) must still fetch it directly.

## App shell

All pages share three primitives in `src/lib/components/shell/`, and new pages
should use them rather than hand-rolling a header:

- `PageHeader` — sticky title bar (`heading` + `text`, plus an `actions` snippet
  for page controls). Its border and frosted background appear only once the
  page has scrolled, so a page at rest reads as one sheet. Pass `children` to
  replace the heading block entirely (the dashboard does this for its hero).
- `PageContent` — the body's stacking rhythm; takes an optional `class` for
  pages that constrain their own width (Settings).
- `SectionCard` — a captioned section: a small title (+ optional subtitle and
  right-side `action`) above a `.card` body. Set `padded={false}` for full-bleed
  bodies.

The sidebar groups navigation by purpose (**Overview** / **Data** / **Setup**)
with Settings, the theme toggle and the rail toggle pinned to the footer. The
rail collapses to icons; that choice is per-device (`quid:sidebar-collapsed:v1`).

## Theme (Paper)

The UI ships one theme in two tones, inspired by Wealthfolio's ink-on-paper
look: **Paper** (light, warm `#FFFCF0` ground) and **Ink** (dark, `#100F0F`).
Both are built from the [Flexoki](https://stephango.com/flexoki) palette.

- **Tokens** live in `src/app.css`. `:root` defines the light tone and `.dark`
  overrides the same names for the dark tone, so components never branch on
  theme. The token names are historical (`--ctp-*`) but their meaning is:
  `mantle` = page, `base` = card, `crust` = sidebar, `surface0` = hover,
  `surface1` = hairline border, `surface2` = field edge, `text`/`subtext*`/
  `overlay*` = ink from strongest to faintest, `accent` = forest green.
- **Switching** is `src/lib/stores/theme.ts` (`light` | `dark` | `system`). It
  toggles the `dark` class on `<html>` and mirrors the choice to
  `localStorage['quid:theme:v2']`. `src/app.html` reads the same key in an
  inline script before first paint, so a reload never flashes the wrong tone —
  **keep those two in sync**. `system` keeps following the OS while the app is
  open. The sidebar footer has a two-way toggle; Settings has the full
  three-way control.
- **Charts** read their colours from the CSS custom properties at render time
  and re-render on theme change via a `MutationObserver` on `<html>`'s
  `class`/`data-theme` (`CumulativeChart.svelte`,
  `analytics/MonthlyTrendChart.svelte`). Use `--ctp-chart-1..6` (forest / sage /
  sand / clay / plum / stone) for series colour, not the raw named colours.
- **Category colour** is user-chosen hex and is often far more saturated than
  the palette. Never paint it raw: set `--cat: <hex>` on the element and use one
  of the role classes from `app.css` — `.cat-chip` (icon tile / pill),
  `.cat-solid` (filled swatch), `.cat-bar` (progress bar). Each `color-mix()`es
  the hue toward the page's ink or ground, and the mix flips with the theme
  automatically. In **charts and ranked lists**, don't use category colour at
  all: call `seriesVar(rank)` (`src/lib/utils/categoryColor.ts`) so a breakdown
  is coloured by position along the theme ramp — arbitrary hues side by side
  read as noise and can't be ordered by eye.
- **Type**: Inter for UI, Merriweather (`font-serif`) for page headings and for
  money set with the `.numeral` class (serif + `tabular-nums`). `HeroAmount.svelte`
  is the page-headline number: it tweens the value and renders the decimal
  fraction in a muted tone.
- **Elevation**: use the `.card` class (hairline border + `--ctp-shadow`).
  Dark-theme drop shadows (`shadow-lg shadow-black/20`) do not belong on paper.

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
