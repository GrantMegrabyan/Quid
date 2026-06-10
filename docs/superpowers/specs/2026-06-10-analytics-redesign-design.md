# Analytics page redesign — insight-first

Date: 2026-06-10
Status: approved (brainstorming session)

## Goal

Replace the current descriptive Analytics page with an insight-first page that
answers two questions directly:

1. **What went up?** — which categories/merchants drove spending above the
   user's own baseline, with drill-down to the evidence (transactions).
2. **Where can I save?** — concrete, heuristic-detected saving opportunities
   (price creep, new recurring charges, habit spend) plus the total cost of the
   recurring stack.

Plus an **on-demand AI narrative** summarising the month in plain language.
Budgets/targets are explicitly out of scope.

## Page structure (top to bottom)

1. **Verdict header** (hero)
   - "May 2026 — £2,140 · +12% vs your 6-month average (£1,905)".
   - Sparkline of the last ~7 complete months.
   - Secondary line: current in-progress month to date + pace projection
     ("June so far: £480, on pace for ~£1,950") — reuses the existing
     `summary` projection fields.
   - Fixed semantics: latest **complete** month vs trailing 6 complete months.
     No period selector here.
2. **AI summary strip** (collapsed)
   - Stored narrative (if any) with "Generated <date> · Regenerate"; otherwise
     a single **Generate** button. Strictly on-demand — no automatic calls.
   - Spinner while generating; API errors (incl. missing OpenRouter key)
     render inline in the strip (same pattern as freeform import — no new
     "is AI configured" endpoint).
3. **"What went up" zone** — diagnosis (see semantics below).
4. **"Where you can save" zone** — three detectors + recurring stack.
5. **Context** — the existing `MonthlyTrendChart`, demoted to the bottom. The
   persisted 3M/6M/12M/All period selector moves here and affects only this
   chart.

### Kept / reworked / cut

- **Kept:** summary endpoint (verdict numbers + projection), monthly-totals
  endpoint + `MonthlyTrendChart`, persisted `analyticsPeriod` store (trend
  chart only).
- **Reworked:** movers → "What went up" vs trailing average with drill-down;
  recurring panel → recurring stack inside the savings zone; large
  transactions → folded into drill-down evidence.
- **Cut (frontend + backend):** category-trends chart, importance trend chart,
  top-merchants chart, distribution card, the 4-KPI tile row, and the
  now-unused endpoints/repo methods: `category-trends`, `category-comparison`,
  `top-merchants`, `importance-breakdown`, `importance-trend`,
  `weekday-breakdown`, `distribution`, `large-transactions`, `recurring`
  (subsumed by `/savings`). Their schemas and components are deleted.

## "What went up" semantics

- **Baseline:** per category, the mean spend over the trailing **6 complete
  months** before the latest complete month (fewer if history is shorter,
  minimum 1). Months with zero spend in the category count as **£0** — divide
  by the window length, not months-with-spend. (An annual bill reads as a
  genuine spike; a paused subscription reads as a low average.)
- **Classification** of latest-complete-month total vs baseline:
  - Increases (delta > 0) sorted by £ delta descending — the main content.
  - **Noise floor:** increases under £10 AND under 10% roll up into a single
    "everything else +£X" line. Constants in code, not settings.
  - Decreases collapse to one muted "What went down" expandable line.
  - A category with spend but no baseline history shows as **"new spending"**
    (never "+∞%").
- **Drill-down** per increase row:
  1. Top 3 contributing merchants in the category (grouped on
     `lower(trim(name))`), each vs its own trailing average in the same
     window; "new" badge when the merchant has no history.
  2. The latest month's transactions for that category, largest first.
- **API:** `GET /api/v1/analytics/diagnosis` returns the entire zone in one
  response: verdict month, baseline window, increases (with contributors and
  transactions inline), rolled-up floor, decreases. Single request, no N+1;
  single-user data volumes make the inline payload cheap.

## "Where you can save" semantics

All detectors build on the existing recurring grouping — (merchant key, exact
amount) present in ≥3 distinct months — scanned over a fixed window of the
trailing **12 complete months**. Thresholds are code constants.

- **Price creep:** merchant with an established recurring charge (≥3 months at
  amount A) followed by a **higher** amount B in ≥2 consecutive months after
  A's last month. Exact-amount grouping keeps variable bills (energy) from
  producing noise. Reports old → new, £/mo delta, annualised delta,
  since-month; sorted by annualised delta. Price drops are not flagged.
- **New recurring:** merchant whose **first-ever transaction** falls within
  the last 4 complete months AND that already forms a recurring group
  (same amount, ≥3 distinct months). The first-ever condition prevents a
  price change double-reporting as "new". Reports £/mo, first-seen month,
  annualised cost.
- **Habit spend:** in the latest complete month, merchants with **≥6
  transactions** and **average ticket ≤ £20**. Top 5 by total. Reports visit
  count, month total, average ticket.
- **Recurring stack:** all currently-active recurring groups (last seen within
  2 complete months), summed to £/mo and £/yr, with an expandable inventory.
  Refinement: a group's monthly estimate is
  `amount × months_covered ÷ months_spanned` (capped at `amount`), so a
  quarterly £90 bill counts as £30/mo.
- **API:** `GET /api/v1/analytics/savings` returns
  `{ priceCreep, newRecurring, habits, recurringStack }`.
- Every detector card has an explicit empty state ("No price increases
  detected in the last 12 months").

## AI narrative

- **Input:** exactly the aggregates the page shows — verdict numbers, top
  increases with contributing merchants, detector findings, recurring-stack
  total. No raw transaction dump.
- **Prompt contract:** 3–6 plain-language sentences; name the biggest driver;
  point at the most concrete saving opportunities; never invent numbers not
  present in the input.
- **Persistence:** new table `analytics_narratives` (migration `0021`; `0020`
  already exists — `app_settings_categorize_model`):
  `id`, `month` (the analysed complete month, unique), `content`,
  `generated_at`, `model`. Upsert per month on regenerate; `GET` returns the
  newest row (null-shaped 200 when none).
- **Endpoints:** `GET /api/v1/analytics/narrative`,
  `POST /api/v1/analytics/narrative` (generate + store + return). Requires
  `QUID_OPENROUTER_API_KEY`; reuses the `QUID_OPENROUTER_*` provider/model.
- **Read-only amendment:** the aggregation repository
  (`repositories/analytics.py`) STAYS read-only. The narrative gets its own
  small repository (`repositories/analytics_narrative.py`) holding the only
  write path. AGENTS.md's "analytics is read-only" note is amended to say
  exactly this.

## Implementation architecture

### Backend

- `repositories/analytics.py`: add `diagnosis()` and `savings()` (both
  read-only); delete dead methods (`category_trends`, `category_movers`,
  `top_merchants`, `importance_breakdown`, `importance_trend`,
  `weekday_breakdown`, `distribution`, `large_transactions`, `recurring`).
  `monthly_totals` and summary support stay.
- `routers/analytics.py` final surface: `/summary`, `/monthly-totals`,
  `/diagnosis`, `/savings`, `/narrative` (GET+POST). Dead schemas removed.
- New `ai_narrative.py` (OpenRouter call, mirrors `ai_freeform.py`).
- New `repositories/analytics_narrative.py` (get/upsert + commit).
- Migration `0021_analytics_narratives`.

### Frontend

- New components: `VerdictHeader`, `AiNarrativeStrip`, `WentUpZone`,
  `SavingsZone` (under `webui/src/lib/components/analytics/`).
  `MonthlyTrendChart` survives. Deleted: `CategoryTrendChart`,
  `CategoryMoversList`, `TopMerchantsChart`, `ImportanceTrendChart`,
  `RecurringPanel`, `LargeTransactionsList`, `DistributionCard`.
- Page load: five parallel GETs (`summary`, `monthly-totals`, `diagnosis`,
  `savings`, `narrative`), no serial phase (diagnosis resolves its own months
  server-side). Keep the out-of-order-response guard (`requestSeq`), drop the
  two-phase complexity.
- `analyticsRepository` reworked to the new endpoint set.

### Empty states

- No complete month yet → verdict header explains; zones hidden.
- Quiet month → "nothing went up meaningfully" in the went-up zone.
- Per-detector zero-findings lines. No blank panels.

## Testing

- **pytest:** baseline math (zero-month counting, noise floor, new-category
  case, shorter-history windows); each detector (incl. "price change must not
  double-report as new recurring", threshold edges); recurring-stack estimate
  scaling; narrative get/upsert with the OpenRouter call mocked; router
  response shapes.
- **e2e (rework `analytics.e2e.ts`):** seed via testing router; assert verdict
  header numbers; expand a went-up row to its transactions; assert savings
  findings; narrative strip shows Generate and surfaces the inline error path
  (e2e backend has no OpenRouter key).
- **Browser verification** per project rules: run migration `0021` against the
  dev DB before the smoke check; load page, exercise expanders + Generate,
  watch network/console.

## Documentation

- `api/README.md`: analytics endpoint list rewritten (remove dead endpoints +
  examples, add `/diagnosis`, `/savings`, `/narrative`).
- `webui/README.md`: Analytics page description updated to the new structure.
- AGENTS.md: analytics section replaced — new semantics, thresholds, the
  read-only amendment, migration note.

## Out of scope (deliberate)

- Budgets / per-category targets.
- Automatic narrative generation (user chose on-demand only).
- A "rising discretionary spend" detector (declined in brainstorming).
- Configurable thresholds (constants in code until proven needed).
