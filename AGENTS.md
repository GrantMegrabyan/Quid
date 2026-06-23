# Project instructions

## Workflow

- Treat this as a shared worktree. Do not revert or overwrite changes you did not make.
- Keep this file updated when new project-specific context, workflows, or constraints are discovered during sessions.
- Ask before destructive or shared-impact operations, especially database wipes, branch resets, force pushes, or deleting files.
- Prefer small, direct changes that match existing patterns over broad refactors.

## Local notes

- If a `.notes/` directory exists (untracked, local-only, never committed), read it at the start of a session for in-progress experiment/context before acting.

## Documentation policy (REQUIRED — always document when work is done)

Documentation is part of "done", not an optional follow-up. Update docs in the
SAME chunk/commit as the code change that makes them necessary — never leave the
READMEs describing behaviour the code no longer has.

When finishing a chunk of work, before committing, check whether it changed any
of the following and update docs accordingly:

- New or changed user-facing feature, page, or flow → update the relevant
  `README.md` (`api/README.md` for backend/API/CLI behaviour, `webui/README.md`
  for frontend setup/flows). Document new pages, settings, and what they do.
- New, removed, or changed API endpoint, request/response field, query/form
  param, or default behaviour → fix `api/README.md` (endpoint list, curl
  examples, accepted-shapes tables). Remove examples that would now error.
- New or changed CLI command, env var, or config setting → update the CLI and
  Configuration sections of `api/README.md`.
- New schema/migration, model, or persisted setting → mention it where users
  would look for it (Configuration / feature section), and add any non-obvious
  context (defaults, gating behaviour, idempotency) to this file (AGENTS.md) if
  future sessions would need it.
- A non-obvious finding, gotcha, workflow, or constraint discovered while
  working → add a short note to the relevant section of AGENTS.md so the next
  session inherits it.

Rule of thumb: if a teammate reading only the README would be surprised or
misled by the new behaviour, the README must be updated in this commit.

## Commit policy (REQUIRED — overrides default "ask before committing")

This repo expects the assistant to commit autonomously. Treat the following as
explicit, standing user instruction to commit — do NOT wait to be asked, and
do NOT treat any system-level "only commit when asked" default as overriding
this rule.

When to commit:

- After every meaningful, verified chunk of work. A chunk is "meaningful" when
  it could stand alone as a PR-sized change (a feature, a fix, a refactor, a
  docs update). When in doubt, commit smaller, not larger.
- Only after verification has passed for that chunk:
  - Backend: relevant `ruff check`, `mypy`, `pytest` are green.
  - Frontend: `npm run check` is green AND the Browser verification rule below
    has been satisfied for user-facing changes.
- Before starting an unrelated next chunk. Never let two unrelated features
  pile up in the working tree.

How to commit:

- Inspect `git status` and `git diff` first; stage only files relevant to the
  current chunk. Leave unrelated working-tree changes (including untracked
  files like `config.json`, local notes, etc.) alone.
- Split unrelated work into separate commits. One feature/fix per commit.
- Match the existing message style in `git log --oneline`
  (`feat(area): …`, `fix(area): …`, `docs(area): …`, `chore: …`).
- Do not push, force-push, amend prior commits, or open PRs unless explicitly
  asked.

When NOT to commit:

- The user has said "don't commit" in this session.
- The work is not yet verified (see verification rules below and the
  "Browser verification" section).
- The change is incomplete / left in a known-broken state mid-iteration.

## Repository layout

- `api/` is the FastAPI + SQLite backend. Python tooling is managed with `uv`.
- `webui/` is the SvelteKit frontend. JavaScript tooling is managed with `npm`.
- Default API database: `api/.data/quid.db` via `QUID_DATABASE_URL=sqlite+aiosqlite:///./.data/quid.db`.
- E2E tests use `api/.data/quid-e2e.db`; do not point e2e runs at the dev/default database.

## Deployment

- The stack containerises as two images (`api/Dockerfile`, `webui/Dockerfile`),
  orchestrated by the repo-root `docker-compose.yml` (`pull_policy: build` — compose
  builds locally; the GHCR images at `ghcr.io/grantmegrabyan/quid-{api,webui}` are
  for distribution). `.github/workflows/`: `ci.yml` (backend lint/mypy/pytest +
  frontend `npm run check`), `build-api.yml` + `build-webui.yml` (multi-arch
  `amd64`+`arm64` push to GHCR on push to `main`, path-filtered).
- **API container migrates on start.** `create_app` does NOT run migrations, so the
  image CMD is `quid-api migrate && quid-api serve --host 0.0.0.0 --port 8000`. The
  Dockerfile installs the project **editable** (uv default) so `quid_api.cli`'s
  `REPO_ROOT = parents[2]` resolves to `/app` and finds `/app/alembic.ini`. SQLite
  DB + logs persist via a `/app/.data` volume. The API runs as **non-root**
  (uid 1001), so the compose uses a **named volume** (`quid-data`) — Docker seeds
  it with the image's ownership. A host **bind mount** would be root-owned and
  fail with `PermissionError: '/app/.data/quid.log'` until `chown 1001:1001`'d
  (the homelab LXC deploy uses a bind mount at `/opt/quid/data` and needed that).
- **UI API URL is RUNTIME, not build-time.** `webui` uses `@sveltejs/adapter-node`
  (`node build`); `httpClient.ts` reads `PUBLIC_API_BASE_URL` via
  `$env/dynamic/public` (the `PUBLIC_` prefix is mandatory to reach the browser).
  Set it in compose `environment:` — no rebuild, image is environment-agnostic. The
  old build-time `VITE_API_BASE_URL` is gone (also renamed in `dev.sh`,
  `playwright.config.ts`, `webui/.env.example`). It must be the **browser-reachable**
  API origin, not the internal compose hostname.
- Deployed stack runs `QUID_ENVIRONMENT=production`, which fails fast unless
  `QUID_ALLOWED_HOSTS` and `QUID_CORS_ALLOWED_ORIGINS` are set (no `*`); the latter
  must include the UI origin. Root `.env` (gitignored) feeds compose.

## Backend notes

- The `/api/v1/testing/*` router (`routers/testing.py`) is DESTRUCTIVE (wipes all
  expenses + categories). It is hardened three ways and all three must be
  satisfied for it to work: (1) mounted only when `QUID_TESTING=true`; (2) every
  request must send `X-Testing-Token` matching `QUID_TESTING_TOKEN` (unset token
  ⇒ fail-closed 403, wrong/missing ⇒ 401); (3) `Settings.validate_testing()` (run
  in `create_app`) refuses startup when `QUID_TESTING=true` and the DB URL doesn't
  contain `test`/`e2e`/`:memory:`, unless `QUID_TESTING_ALLOW_UNSAFE_DB=true`. The
  Playwright harness sets the token in `webui/playwright.config.ts` and sends it
  from `webui/tests/helpers.ts`; backend `app_client` fixture sets/sends
  `test-token`. If you add a testing route or a new caller, send the header.
- Run backend commands from `api/`.
- Common verification:
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy`
  - `uv run pytest`
- Use Alembic migrations for schema changes under `api/alembic/versions/`.
- Transactions are represented as `expenses` in the schema/code.
- `expenses.date` is a TEXT column that stores EITHER a bare `YYYY-MM-DD` date
  OR a full `YYYY-MM-DDTHH:MM:SS` local timestamp (no tz). The `ck_expenses_date_iso`
  CHECK accepts both (migration `0019`); there is intentionally no midnight
  backfill of legacy date-only rows. Lexical sort and the 10-char day prefix
  treat both forms correctly. Expense date inputs are validated with
  `datelib.validate_iso_datetime` (accepts date OR datetime); rule date bounds
  (`match_date_from/to`) and Amazon `order_date` keep the strict date-only
  `validate_iso_date` — DO NOT widen those, their DB CHECKs are date-only.
- Import dedupe key is `(date, lower(trim(name)), amount)` where `date` is the
  full stored value (with time when present). Same merchant/amount on the same
  day but different times → distinct rows; re-importing the same timestamped CSV
  → no-op. Caveat: a row imported once date-only then re-imported from a richer
  export WITH a time gets a different key and inserts a duplicate (preview won't
  flag it) — re-import only new periods, or wipe + re-import, when adopting
  timestamped exports.
- CSV fee column (`_FEE_ALIASES` = `fee, fees`, optional): when present, the
  parsed fee is folded into the amount **magnitude** (sign-aware:
  `amount - abs(fee)` for spend/`amount <= 0`, `amount + abs(fee)` for positive
  rows) in `csv_import.parse_csv`. This is what makes a Revolut fee-only row
  (`Amount=0.00, Fee=7.99`) import as a 7.99 spend instead of being dropped as
  "Amount is zero"; the zero-check runs AFTER folding in the fee. Keep the sign
  asymmetry so refund/income sign-detection downstream still sees the right
  direction. A non-numeric fee is a per-row skip (`Fee “…” is not a number`).
- CSV date column preference: `_DATE_ALIASES` order is `date, started date,
  completed date, …` so Revolut-style statements (which have both) use **Started
  Date**, and `csv_import._normalize_date` PRESERVES the time component.
- Import-rule date matching (`import_rules._matches_date`) compares on the
  expense date's 10-char day prefix so an inclusive `match_date_to` still matches
  a timestamped transaction on the boundary day. Keep the prefix slice if you
  touch it.
- Incoming money & refunds (`refund_detection.py`, wired into BOTH
  `preview_import_csv` and `import_csv` in `routers/expenses.py`): the expense
  model is sign-less, so the **sign of the parsed amount** drives money
  direction. After AI exclusion, the router runs `detect_refund_pairs` then
  `detect_income_indices`; `excluded_indices = ai | refunds | income`.
  - `detect_refund_pairs` returns indices for BOTH the credit AND its matched
    charge (it used to return only the credit, which kept the charge as spend —
    a double-count bug; do NOT revert that). Batch-local, exact-amount, greedy
    1:1, nearest-date, within `settings.refund_window_days`
    (`QUID_REFUND_WINDOW_DAYS`, default 60). Counted as `skippedRefunds`.
  - `detect_income_indices` is "every remaining `amount > 0` row" (salary,
    transfers in, reimbursements). Subtract `refund_indices` first so refund
    credits count as refunds, not income. Counted as `skippedIncome`.
  - Both surface in the preview as `kind="excluded"` rows (never dropped
    silently). Don't lean on Monzo's `Money In`/`Money Out` columns — Revolut has
    only a signed `Amount`; the sign is the bank-agnostic signal.
  - Deliberately deferred: cross-import / DB-backed refund matching, partial
    refunds, non-signed "Paid In/Out" formats, any visible income view (needs a
    `direction` column + dedupe-key change + relaxing `ck_expenses_amount_positive`),
    and a keep-income settings toggle. Don't implement these as part of routine
    import work.
- Use `uv run quid-api clear-transactions` for the built-in transaction wipe, but only after explicit confirmation.
- Import rules: a rule's `set_display_name` and `set_note` are only meaningful
  for `categorize` rules (an `exclude` rule deletes the matched expense), and the
  rules UI hides both fields for `exclude`. Both import-time (`expenses.py`) AND
  re-apply (`import_rules.py` `apply_to_existing` / `apply_all_to_existing`) set
  `expenses.display_name` / `expenses.note` when the matched rule has
  `set_display_name` / `set_note`. `set_note` OVERRIDES any note from the import
  row (CSV/freeform) or the existing expense's note on re-apply (same semantics
  as `set_display_name`). When changing rule application, keep all three paths in
  sync for both fields.

## Frontend notes

- Transient feedback is global: one `ToastHost` (`webui/src/lib/components/
  ToastHost.svelte`) mounted in `+layout.svelte`, driven by
  `webui/src/lib/stores/toasts.ts`. Use `notify('success'|'error', msg)` for
  banners; do NOT add per-page fixed banners (they overlap the toast host). The
  toast carries `data-testid="app-toast"` + `data-kind` (e2e assert on those,
  NOT the old per-page `amazon-banner`/`cascade-notice`, which were removed).
- Destructive deletes are Gmail-style (immediate + Undo, no confirm dialog) via
  `softDelete({ kind, id, message, commit })`. It is **deferred execution**: the
  row is hidden by adding `pendingKey(kind,id)` to the global `pendingDeletes`
  set (every deletable list filters that set out — Amazon orders, expenses,
  categories, import rules, AI rules), and the real `commit()` (the API DELETE)
  runs only when the undo window lapses, the toast is dismissed, or the user
  navigates/unloads (`beforeNavigate`+`beforeunload` flush in the layout). Undo
  cancels before any request — so a category cascade is free to reverse; its
  reassignment count is reported via `notify` only after commit. When adding a
  new deletable list, add the `pendingDeletes` filter to its `{#each}` AND route
  its delete through `softDelete` (don't call the store delete directly), or the
  row won't hide. Confirm-dialog testids (`*-delete-confirm-btn`,
  `*-delete-cancel-btn`) are gone.
- Form fields share two component classes in `webui/src/app.css` (`@layer
  components`): `.field` (the canonical input style — `rounded-md` border,
  `bg-ctp-base`, `px-3 py-2 text-sm`, accent focus ring) for text inputs and
  textareas, and `.field` + `.field-select` for native `<select>`s
  (`.field-select` adds `appearance-none` + a custom SVG chevron so selects match
  inputs). Use these instead of re-pasting inline Tailwind on new fields. Append
  per-instance modifiers inline (`w-full`, `resize-none`, `pl-9` for a leading
  icon, `disabled:*`); utilities win over the component layer, so a trailing
  `text-xs` overrides `.field`'s `text-sm`. Intentionally NOT migrated:
  checkboxes, file/color inputs, the Amazon in-card pill `<select>` /
  short-name `<input>`, and the import preview amount editor (conditional error
  border).
- Persisted view state (the month being viewed, the active Import tab) uses the
  reusable `persisted<T>(key, initial, validate?)` store in
  `webui/src/lib/stores/persisted.ts` — a `localStorage`-mirrored `writable`
  that is SSR-safe (`browser`-guarded) and falls back to `initial` on
  missing/malformed/invalid stored values. Prefer it over ad-hoc `localStorage`
  for new persisted UI state; use a namespaced, versioned key (`quid:<thing>:vN`)
  so a future shape change degrades to the default instead of crashing. The
  dashboard's chart-toggle/group-by prefs still use their older bespoke
  `expense-tracker:*` keys (not yet migrated). NOTE: persisting a value the e2e
  suite relies on resetting between tests can cause cross-test bleed — keep
  persisted keys to genuinely user-facing view state.
- Run frontend commands from `webui/`.
- Common verification:
  - `npm run check`
  - `npm run build`
  - `npm run test:e2e` for any user-facing change (see "Browser verification" below).
- `npm run format` currently may fail if Prettier/Tailwind looks for `src/routes/layout.css`; do not assume formatting failures are caused by the current change without reading the output.

## Browser verification (REQUIRED for user-facing changes)

Type-check + build are not enough. They miss runtime errors (e.g. missing DB
migrations, 500s on data load, broken layouts, click handlers that throw).
Any change that touches the UI, an API endpoint, a schema/migration, or the
data shape consumed by the UI MUST be verified end-to-end before reporting
done.

Use one of these, in order of preference:

1. **Playwright e2e** (`npm run test:e2e` from `webui/`). The config in
   `webui/playwright.config.ts` boots its own API on port 8001 against
   `api/.data/quid-e2e.db` and its own preview server on 4173, so it is safe
   to run repeatedly. Add or update an `*.e2e.ts` test under `webui/tests/`
   when the change introduces new user-facing behavior (new fields, new
   flows, new error states). Existing examples: `categories.e2e.ts`,
   `expenses.e2e.ts`.
2. **Interactive Playwright via the agent-browser skill** for ad-hoc smoke
   checks (load the page, watch network for non-2xx, click the affected
   controls, read console errors). Prefer this over guessing, especially
   after migrations or schema changes.

Verification checklist for any user-facing change:

- Load the affected page(s) and confirm no 4xx/5xx in the network log.
- Exercise the new/changed controls (submit, edit, apply, delete) and
  confirm the expected DOM update.
- If a migration was added, confirm `uv run alembic upgrade head` was run
  against the dev DB (`api/.data/quid.db`) before the smoke check — a
  passing `pytest` suite uses a throwaway DB and will not catch a stale dev
  DB causing 500s in the running app.
- Capture and report any console errors observed.

## Category/AI categorisation context

- Default categories live in both `api/src/quid_api/seed.py` and `webui/src/lib/repos/seed.ts`; keep them aligned.
- Category descriptions are sent to AI categorisation. Keep descriptions concise and include both "belongs here" and "does not include" guidance when useful.
- AI categorisation should strongly prefer existing categories and only create a new category when no existing guided category reasonably fits.
- The two AI features are gated by persisted app settings, not per-request flags:
  `ai_categorize_enabled` and `ai_short_names_enabled` (both default true, on the
  `app_settings` singleton, edited via the Settings page / `PATCH /api/v1/settings`).
  CSV import (`/api/v1/expenses/import-csv[/preview]`) reads `ai_categorize_enabled`
  server-side — there is no longer an `ai_categorize` form param (passing it 422s).
- Both AI features reuse the same OpenRouter provider/model
  (`QUID_OPENROUTER_*`); short names live in `api/src/quid_api/ai_short_names.py`.
- `ai_categorization._snap_to_existing` normalises an AI category suggestion back
  onto an existing category to fight category proliferation. It snaps ONLY on
  provable equivalence: exact (whitespace/case) match, then a normalised key that
  ignores connectors/punctuation and word order (`Food & Drink` == `Food and
  Drink` == `Drink & Food`; stopwords `and/the/of/&`, strip chars `&/,.()-`). It
  intentionally does NOT do token subset/superset "paraphrase" merging — token
  heuristics can't distinguish desirable filler (`Dining Out`→`Dining`) from a
  meaningful qualifier (`Travel Insurance`→`Travel`), and a wrong merge hides a
  transaction under the wrong label (costlier than a duplicate category a user
  can edit). If you make snapping fuzzier, keep that asymmetry.
- The AI's `confidence` (0–1) per row is now USED, not just logged: an
  `exclude=true` is only honoured when `confidence >= _MIN_EXCLUDE_CONFIDENCE`
  (0.5). A low-confidence exclude is skipped (row kept + still categorised) and
  logged `ai.categorize.exclude_skipped_low_confidence`, because excluding drops
  the transaction from the import entirely — the most costly model mistake. The
  per-run summary log carries `excludes_skipped_low_confidence=N`.

## Amazon orders context

- Amazon orders are imported from CSV (`POST /api/v1/amazon-orders/import-csv`) and
  linked to `expenses` via the `expense_amazon_orders` many-to-many table.
  Auto-matching runs on import and via `/match-all`.
- Auto-matching (`AmazonOrderRepository.auto_match_all`) is two passes: pass 1
  links each unmatched order to its sole matching expense; pass 2
  (`_run_combined_pass`) sums 2..`_COMBINED_MAX_SIZE` (3) nearby orders to a
  single combined bank charge. Pass 2 is bounded and MUST stay that way — it
  used to enumerate global combinations over every unmatched eligible order
  (O(n^3+) → hangs on large histories). `_generate_combos` now (a) partitions
  candidates into the `_COMBINED_ORDER_DATE_SPAN_DAYS` (2) date windows via a
  binary search on the date-sorted list and anchors each combo at its earliest
  member (so each combo is generated once and never crosses a window), and (b)
  is hard-capped by two settings: `QUID_AMAZON_COMBINED_MAX_WINDOW_ORDERS`
  (default 60 — a denser single-date window is a pathological cluster and is
  skipped wholesale) and `QUID_AMAZON_COMBINED_MAX_COMBINATIONS` (default 50000
  — global ceiling; generation stops once reached). Both caps log a WARNING
  (`amazon.combined.window_capped` / `amazon.combined.combination_capped`) when
  they engage. The defaults are generous enough that ordinary small histories
  produce the identical combo set as before; only set them lower to be more
  aggressive on huge imports. Perf tests in `tests/test_amazon_orders.py`
  (`test_generate_combos_*`, `test_combined_pass_dense_window_ingest_is_bounded`,
  `test_combined_match_pass_scales_to_*`) prove bounded runtime on
  thousands of orders and MUST keep passing.
- The import pipeline's shared seam is
  `_ingest_orders(session, parsed_orders, *, source=...)` in
  `routers/amazon_orders.py` (upsert → AI short-names → AI categorize →
  `auto_match_all` → commit). A new source just produces `list[ParsedOrderInput]`
  and calls it. CSV passes `source="csv"`; the browser export passes
  `source="export"`. `source` is provenance for logging only (no per-order
  column). CSV is the canonical fallback and must not be removed/regressed.
- `POST /api/v1/amazon-orders/import-export` ingests browser-scraped orders as
  JSON (`AmazonExportRequest`, camelCase). **MONEY-AS-STRINGS contract:** order
  `total`, item `price`, shipment `total` are JSON strings (`"19.99"`), never
  numbers — typed `str` in the schema so a number is a hard 422; the matcher
  does exact `Decimal` equality. Row-level bad data (blank id, non-importable
  status, bad date, missing/≤0 total) is SKIPPED per-order with a reason
  (returned in `files[0].skipped`); only structural payload errors 422 (mirrors
  CSV). Order ids are deduped (last wins) before ingest.
- The webui scraper lives in `webui/src/lib/amazon/`. `scraper.ts` is the
  canonical, fixture-tested (`webui/tests/amazon-scraper.e2e.ts`) pure parser
  (`parseOrdersFromDocument(doc, domain)`); it is **fail-loud** on DOM drift
  (throws `AmazonScrapeError` when an orders-shell yields zero cards or a card
  lacks an id/total — never emits truncated/garbage data). `bookmarklet.ts` is a
  self-contained `javascript:` derivative (no remote fetch/eval; runs in the
  amazon.* origin, downloads a `.json` + copies to clipboard) and MUST be kept
  in sync with `scraper.ts`. The "Import from browser" panel on `/amazon`
  uploads/pastes that JSON same-origin to `/import-export` (CORS blocks a direct
  amazon.*→API POST by design; don't relax it).
- Each order has a `short_name` (≤60 chars): a brief AI-generated description of what
  was purchased, generated ONCE at import time (only when `ai_short_names_enabled`)
  and stored. Re-importing the same order id never overwrites it. Users edit it via
  `PATCH /api/v1/amazon-orders/{id}/short-name`. When AI short names are disabled the
  field is left blank on import (no AI call, no title fallback).
- A linked Amazon order's `short_name` surfaces as the transaction's note in the
  expense list when the expense has no note of its own.
- Backfill names for already-imported orders missing one with
  `uv run quid-api backfill-amazon-short-names` (idempotent; never overwrites). It
  calls OpenRouter, so it needs `QUID_OPENROUTER_API_KEY`.
- Each order also has a `category_id` (nullable FK, AI-derived from item titles,
  generated ONCE at import when `ai_categorize_enabled`; re-import never
  overwrites a non-null one). Order matching is restricted to Amazon-merchant
  expenses (`Expense.name` matching `amazon`/`amzn`/`amz`); manual `/link` is
  unrestricted.
- Expense category provenance lives in `expenses.category_source` (priority
  high→low: `manual` > `rule` > `amazon` > `ai` > `import`). An Amazon order's
  category overrides an expense category ONLY when its source is `ai` or
  `import` (so the coarse expense-AI "Shopping" gets replaced by the precise
  per-order category, but `manual`/`rule` choices are protected). Set source on
  every expense write path; the category-delete cascade resets to `import`.
- `uv run quid-api backfill-amazon-categories` AI-categorises orders missing a
  category AND runs a standalone propagation pass over ALL categorised orders
  (because `set_generated_categories` only propagates for orders it newly
  categorises — orders categorised earlier whose linked expense is still
  `ai`/`import` need the standalone pass). Idempotent; needs `QUID_OPENROUTER_API_KEY`.

## Adding transactions / Import page context

- The webui **Import** page (`webui/src/routes/import/+page.svelte`) is the SINGLE
  entry point for adding transactions, with three tabs: **CSV file**, **Single
  transaction**, **AI free-form**. The dashboard only EDITS existing expenses
  (`ExpenseFormModal` is opened in edit mode only); its empty state links to
  `/import`. Don't reintroduce an "add" affordance on the dashboard.
- The single-add tab is plain (no AI) and `POST`s to `/api/v1/expenses`. Its
  amount input must use `value=` + `oninput` (string), NOT `bind:value` on a
  `type=number` field — `bind:value` coerces to a number and `parseAmountInput`
  expects a string (`.trim()`), which throws and silently aborts submit.
- AI free-form import: `POST /api/v1/expenses/import-freeform/preview` (body
  `{rawInput}`) parses text via OpenRouter (`api/src/quid_api/ai_freeform.py`),
  then reuses the SAME categorisation + preview helpers as CSV
  (`_categorize_if_requested`, `_prepare_preview_items`, `_build_preview_rows`)
  with a synthetic `_ParsedUpload` (filename `AI free-form`). Confirm is
  `/import-freeform/confirm`; both CSV and free-form confirm share
  `_confirm_import(...)` in `routers/expenses.py`, parametrised by
  `source`/`raw_input`. Free-form requires `QUID_OPENROUTER_API_KEY`.
- `import_logs` now has `source` ('csv'|'freeform', CHECK-constrained, default
  'csv') and a nullable `raw_input` (the submitted free-form text; NULL for CSV).
  Migration `0017`. `GET /api/v1/import-logs` exposes them as `source`/`rawInput`;
  the Import history table shows a Source column + expandable raw input.

## Analytics context

- The **Analytics** page (`webui/src/routes/analytics/+page.svelte`) is
  insight-first: verdict header → on-demand AI narrative strip → "What went
  up" (diagnosis) → "Where you can save" (savings detectors) → monthly trend
  chart (the only thing the persisted 3M/6M/12M/All period selector affects —
  and it windows CLIENT-SIDE from all-history monthly totals; one parallel
  load on mount, no reload on period change).
- Backend surface is exactly: `/summary`, `/monthly-totals` (optional
  date_from/date_to window) and `/diagnosis`, `/savings`, `/narrative`
  (GET+POST), the last three anchored on the latest COMPLETE month via a
  required `as_of` (the client's today; GET `/narrative` is the exception —
  it just returns the latest stored row, no params). The old
  category-trends/comparison/top-merchants/importance/weekday/recurring/
  large-transactions/distribution endpoints are GONE — don't resurrect them.
- The aggregation repository (`repositories/analytics.py`) is READ-ONLY (no
  commit). The ONE analytics write path is the stored AI narrative:
  `repositories/analytics_narrative.py` (one row per month, upsert on
  regenerate; table `analytics_narratives`, migration `0021`), written by
  `POST /analytics/narrative` which builds a JSON facts payload from
  diagnosis+savings and calls `ai_narrative.generate_narrative` (OpenRouter,
  `QUID_OPENROUTER_*`, 422 without a key). Generation is strictly on-demand —
  never generate automatically.
- Diagnosis semantics: latest complete month vs each category's trailing
  ≤6-complete-month average where zero-spend months count as £0 (divide by
  window length, not months-with-spend). Increases below £10 AND 10%
  (`_NOISE_FLOOR_*`) roll into "everything else"; new categories have
  `percentChange=null`. Contributors compare each merchant
  (`lower(trim(name))`) to its own baseline, top 3 by delta.
- Savings detectors (constants in `repositories/analytics.py`): scan trailing
  12 complete months on the (merchant, exact amount, ≥3 distinct months)
  recurring grouping. Price creep = established group then a HIGHER amount in
  ≥2 CONSECUTIVE months after it. New recurring = recurring group whose
  merchant's first-EVER transaction is within the last 4 months (this is what
  stops a price change double-reporting as new). Habits = ≥6 txns at ≤£20 avg
  in the latest month. Stack estimate = `amount × monthsCovered ÷ span`
  (capped at amount) so quarterly bills don't read as monthly.
- Month grouping uses the `YYYY-MM` prefix of the date string (works for both
  date-only and timestamped dates). `_month_add`/`_months_between` do calendar
  month arithmetic on `YYYY-MM` keys.
- Charts: only `MonthlyTrendChart` survives on this page (chart.js +
  theme-observer pattern; `CumulativeChart` still serves the dashboard). The
  e2e spec is `webui/tests/analytics.e2e.ts`; it asserts on
  `analytics-verdict*`, `analytics-wentup*`, `analytics-creep-item`,
  `analytics-newrecurring-item`, `analytics-habit-item`, `analytics-stack-*`,
  `analytics-narrative*` testids.
- The narrative POST holds its read transaction open across the OpenRouter call (up to ~60s); harmless single-user, but if a concurrent writer ever deadlocks here, rollback before the AI call is the fix.
- The e2e Playwright harness pins QUID_OPENROUTER_API_KEY='' for the e2e API (webui/playwright.config.ts) so e2e runs are hermetic — env beats api/.env in pydantic-settings. Don't remove that override; AI-path e2e tests rely on the deterministic missing-key 422.
