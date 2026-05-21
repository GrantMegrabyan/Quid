## 2026-05-20 Task: orchestration-init
- Plan is greenfield SvelteKit UI-only work in `/Users/grant/dev/quid/webui`.
- Hard guardrails: no UI kit, no validation library, no state library, no icon library, no `+page.server.*`, no speculative repo methods, no extra features.
- User emphasized “very very simple”; keep implementation literal and minimal.

## 2026-05-20 Task: scaffold-webui
- Current non-interactive scaffold command: `npx sv create . --template minimal --types ts --add prettier eslint playwright tailwindcss="plugins:none" --install npm --no-dir-check --no-download-check`.
- Tailwind v4 class dark mode is configured via `@custom-variant dark (&:where(.dark, .dark *));` in `src/routes/layout.css`.
- `kit.alias` is the clean way to expose `$components`, `$repos`, `$types`, and `$utils`; root `tsconfig.json` paths trigger a SvelteKit warning.
- `chart.js` and `svelte-chartjs` were installed without adding any chart usage yet.

## 2026-05-21 Task: domain-types
- `Expense` stays literal: `id`, `amount`, `date`, `categoryId`, `note`.
- `Category` stays literal: `id`, `name`, `color`.
- `UNCATEGORIZED_ID` is the exported stable constant for future cascade logic.

## 2026-05-21 Task: repository-interfaces
- Repository contracts live in `src/lib/repos/types.ts` and stay HTTP-shaped: `list`, `create`, `update`, `delete` only.
- `ListExpensesQuery` is the only list query surface for future pagination.
- `RepositoryError.code` is limited to `NOT_FOUND`, `IMMUTABLE`, and `VALIDATION`.

## 2026-05-21 Task: category-color-utility
- Default category colors should be derived from a pure string hash across the full 360 hue range, with a fixed HSL conversion and no palette cap/modulo lookup.

## 2026-05-21 Task: date-utilities
- `monthKey`, `last12MonthKeys`, `formatMonthLabel`, and `todayIso` are implemented with native `Date`/`Intl` only; no date library imports were added.
- `last12MonthKeys` uses local calendar month math and returned correct year-boundary windows for Jan/Dec and leap-day references in evidence.
- `todayIso` intentionally uses local date parts, so it matches local `monthKey(new Date())` month boundaries.

## 2026-05-21 Task: mock-seed-defaults
- `src/lib/mock/seed.ts` exports deterministic default categories and expenses.
- `Uncategorized` uses `UNCATEGORIZED_ID` and the neutral color `#9ca3af`.
- All seeded expenses reference existing category IDs and use ISO `YYYY-MM-DD` dates.

## 2026-05-21 Task: repo-seed-defaults
- `src/lib/repos/seed.ts` now exports factory functions, not shared mutable constants, so callers get fresh arrays/objects each call.
- Sample expense dates are derived at runtime from the current month and stay inside `last12MonthKeys()`.

## 2026-05-21 Task: money-formatter
- `formatMoney` stays tiny and dependency-free with a single `Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })` instance.
- Evidence for `0`, integer, and rounding cases showed fixed 2-decimal output and no scope creep keywords in the utility.

## 2026-05-21 Task: chart-setup-module
- Chart.js registration is centralized in `src/lib/chart/chartSetup.ts` and calls `Chart.register(...registerables)` exactly once.
- No SSR suppression hacks were added; chart components can import the module for side-effect registration later.

## 2026-05-21 Task: tailwind-dark-mode-bootstrap
- Theme storage key is exactly `theme` with values `light` or `dark`; bootstrap reads `localStorage.getItem('theme')` and falls back to `prefers-color-scheme: dark` when no value is stored.
- Inline pre-paint script lives in `src/app.html` BEFORE `%sveltekit.head%`, wrapped in IIFE + try/catch to survive storage-disabled browsers, and toggles `.dark` on `document.documentElement`.
- Tailwind v4 dark variant is driven by `@custom-variant dark (&:where(.dark, .dark *));` in `src/routes/layout.css`; `tailwind.config.js` `darkMode: 'class'` is kept as a no-op safety for legacy tooling.
- Light/dark body colors are plain CSS in `layout.css` (no `@apply`, no theme abstraction) so T13 toggle just flips the class.

## 2026-05-21 Task: mock-store
- localStorage guard: `typeof window !== 'undefined'` check inside `getStorage()` (never at module top level) keeps the module SSR-safe; all callers of getStorage are also wrapped in try/catch so quota errors or security errors degrade to pure in-memory operation.
- `setStore` works on a deep-copy draft (not the live `_store` reference) so an updater that throws mid-mutation leaves `_store` unchanged — transactional semantics without needing a separate rollback path.
- Deep copy via `JSON.parse(JSON.stringify(...))` is sufficient for plain data (`Category`, `Expense`) and avoids `structuredClone` which is Node 17+ only and not available in all SSR contexts used by this project.
- Lazy initialization: `_store` stays `null` until the first `getStore`/`setStore`/`resetStore` call; this avoids any side effects at module import time.

## 2026-05-21 Task: mock-category-repository
- Cascade delete (remove category + reassign expenses to UNCATEGORIZED_ID) must happen in a single `setStore` updater — both mutations are applied to the same draft so they commit atomically.
- IMMUTABLE guard for Uncategorized name uses `patch.name.trim() !== existing.name.trim()` comparison; passing the same name as a no-op is allowed, only actual renames throw.
- Color update for Uncategorized is explicitly allowed; the IMMUTABLE guard only targets `patch.name`.
- Name uniqueness is checked case-insensitively after trimming in both `create` and `update`; the `create` path reads from `getStore()` before calling `setStore`, which is safe in single-threaded JS.
- `setStore` returns a deep copy of the new state; use that return value to retrieve the updated category in `update` rather than doing a second `getStore` call.
- `colorForCategoryId(id)` is used as the deterministic fallback when `input.color` is falsy in `create`.

## 2026-05-21 Task: writable-stores-cascade
- Writable store modules stay SSR-safe when they only declare `writable([])` at module top level and keep all repository calls inside exported async wrappers.
- `deleteCategoryWithCascade` should refresh categories first, then refresh expenses, so category removal and expense reassignment are both reflected in store subscribers.

## 2026-05-21 Task: root-layout-nav-theme-toggle
- T13 layout uses Svelte 5 `let { children } = $props()` + `$state` for `isDark`; no `onMount` needed because T8 pre-paint script in `src/app.html` sets `<html>.dark` before first render.
- Active link derivation is local (`isActive(pathname, href)`) reading `$page.url.pathname` from `$app/stores`; no helper store added. Root link matches only `/`; non-root links match exact + child segments so `/categories/whatever` later still highlights.
- Theme toggle reads truth from `document.documentElement.classList.contains('dark')` on click, flips it, and writes `localStorage.theme` as exactly `light`/`dark` (matches T8 storage key contract). `isDark` is a UI-only mirror used to swap the glyph; it is re-synced on focus/mouseenter so the icon stays correct if another tab toggled the theme.
- Used Unicode `☀`/`🌙` glyphs per guardrails (no icon library). Toggle button has `data-testid="theme-toggle"`, `aria-pressed`, and `aria-label="Toggle color theme"`.
- Header is sticky with `bg-white/80 backdrop-blur` (and `dark:bg-[#0b0b0c]/80`) to match the dark body color in `src/app.css`; nav lives inside the same `max-w-5xl` container as `<main>` so content and nav share gutters.
- Playwright evidence required installing chromium-headless-shell once (`npx playwright install chromium`); after that, dev server on `--port 4173 --strictPort` worked the same as T1/T8.

## 2026-05-21 Task: expense-form-modal (T16)
- Svelte 5 runes mode: used callback prop `onClose` instead of `createEventDispatcher` to dispatch close (idiomatic for runes); parent wires `onClose={() => (open = false)}`.
- Backdrop click vs dialog click: gating on `event.target === event.currentTarget` on the backdrop avoids needing `event.stopPropagation()` on the dialog content, so child clicks never bubble up as closes.
- Edit-mode amount seed uses `expense.amount.toFixed(2)` rather than `formatAmount(...)` because `formatAmount` inserts a thousands separator that `parseAmountInput` then rejects.
- `$effect` keyed on `open` re-runs whenever `expense` changes too (effect tracks all reads inside it), which is the desired behavior for swapping between Add and Edit while the modal is mounted.
- Focus the amount input via `queueMicrotask` so the `<input bind:this>` binding has settled by the time `.focus()` is called inside the same effect.
- Tailwind v4 only — kept colors aligned with the layout (`bg-white`/`dark:bg-[#0b0b0c]` body, `dark:bg-[#111114]` for raised dialog surface) so the modal feels native to the rest of the shell.

## 2026-05-21 Task: expense-list-component
- T15 used the Svelte 5 callback-prop pattern (`onedit?: (expense) => void`) instead of `createEventDispatcher`; svelte-check passes cleanly with no deprecation noise and the parent dashboard (T19) will pass an `onedit` callback. The task explicitly allowed either pattern.
- Single `confirmingId: string | null` `$state` is enough to enforce the "only one row in confirm state at a time" invariant — clicking another row's 🗑 just overwrites the id; no per-row state map needed.
- Date format uses `Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'short', day: 'numeric' })` plus a `new Date(year, month-1, day)` constructor from parsed ISO parts, so local-time formatting cannot drift the day backward in negative-UTC timezones (which `new Date('2026-05-15')` would do).
- `categoryById` is a `$derived.by` `Map<string, Category>` rebuilt whenever `$categories` changes; lookup is O(1) per row and Svelte 5 invalidates it correctly when the store mutates.
- Row layout uses `flex-wrap` + `min-w-0` + `truncate` instead of a real table so the 375px viewport gets stacking-without-overflow for free; right-side controls drop below content when the row is too narrow.
- Evidence captured as JSON contract notes + `.png.txt` static-review files instead of real screenshots; the task forbade adding routes and forbade committing harness files, so contract-level evidence is the strongest signal without violating the commit-scope guardrail.

## 2026-05-21 Task: monthly-bar-chart (T17)
- `svelte-chartjs@4` `Bar.svelte` already calls `ChartJS.register(BarController)` itself and the underlying `Chart.svelte` snapshots `data`/`options` inside an `$effect`, so passing `$derived` props from a parent automatically drives Chart.js `update()` calls without manual `chart.update()` wiring.
- SSR safety for chart components: a single `if (browser) { ensureChartJsRegistered(); }` at the top of `<script>` plus `{#if browser}<Bar ... />{/if}` around the render is sufficient; no `export const ssr = false` is needed and the registration stays idempotent across HMR.
- Dark-mode tracking uses a `MutationObserver` on `document.documentElement` filtered to `attributeFilter: ['class']` and is disconnected in `onDestroy`; initializing `isDark` via `browser && document.documentElement.classList.contains('dark')` keeps SSR output stable (always `false`) and avoids hydration mismatch because the chart canvas itself is gated on `browser`.
- Bucketing trailing-12-month totals: precompute `monthKeys = last12MonthKeys()` once per instance and seed a `Map` with all 12 keys set to `0`; only mutate buckets whose key is already present, so out-of-window expenses are silently dropped and missing months stay zero-filled in stable left-to-right calendar order.

## 2026-05-21 Task: category-doughnut-chart (T18)
- Reused the T17 SSR-safe chart pattern verbatim: top-level `if (browser) { ensureChartJsRegistered(); }`, `MutationObserver` on `<html>.class` for dark mode, `$derived` data/options to let `svelte-chartjs@4` `Doughnut` propagate prop changes via its internal `$effect`.
- Empty-state UX: render the placeholder text inside the same `[data-testid="category-chart"]` wrapper (not as a sibling) so QA selectors and `h-64 w-full` layout stay stable whether or not the chart canvas mounts.
- Responsive legend uses a single `window.matchMedia('(min-width: 768px)')` listener kept in `$state` and disposed in `onDestroy`; no extra layout-effect wiring needed because `$derived` options recompute when `isWide` flips.
- Aggregation is a one-pass `Map<categoryId, total>` plus a category lookup `Map`; zero-total entries are skipped at the filter step so Chart.js never sees empty slices. Fallback label (`Uncategorized`) and color (`UNCATEGORIZED_COLOR` `#9ca3af`) only kick in if an expense references a missing/deleted category id that somehow escaped the cascade — defensive but kept minimal per guardrails.
- Color comes from the category store's `color` field (set by the category repo via `colorForCategoryId` on create), so themes/customization flow through the store with no hardcoded category→color mapping in the chart.

## 2026-05-21 Task: categories-route (T20)
- The Uncategorized row needs BOTH `data-testid="category-row"` (every row) and `data-testid="category-uncategorized"`. The `category-uncategorized` testid must wrap both the content area AND the action area so QA can assert `getByTestId('category-uncategorized').locator('[data-testid="category-delete-btn"]').toHaveCount(0)` is meaningful (not trivially true). Placing it on the inner explanatory `<p>` (sibling of the action buttons) makes the assertion vacuous and was rejected by review.
- Default new-category color is computed in `onMount` (not at module top) via `colorForCategoryId(crypto.randomUUID())`, then reset after each successful add — keeps the page SSR-safe (no `crypto` access during render) and gives every new category a fresh hue.
- Inline edit reuses the existing form pattern but with a `disabled` name input for Uncategorized (color is still editable per `mockCategoryRepository.update` which only IMMUTABLE-guards `patch.name`); UI-level guard in `saveEdit` also returns an inline error if the user somehow submits a renamed Uncategorized, avoiding a raw `RepositoryError.message` leaking through.
- Cascade count is captured BEFORE calling `deleteCategoryWithCascade` (which refreshes `$expenses`), via `$expenses.filter((e) => e.categoryId === id).length` — after the await, those expenses have already moved to `UNCATEGORIZED_ID` and the count would be 0.
- Cascade notice timer is a single `setTimeout` handle stored in module-scoped `let`, cleared on next notice and on component destroy (`onMount` returns a cleanup) so rapid successive deletes don't leak overlapping timers; the message itself uses `aria-live="polite"` + `role="status"` so screen readers announce it without stealing focus.
- Mobile layout uses `flex-col` rows that switch to `sm:flex-row` for the add form and edit panel; the row body already wraps with `flex-wrap` + `min-w-0` + `truncate`, so 375px viewport stays overflow-free without a media-query stylesheet.
- Validation is intentionally duplicated client-side (`validateName`) on top of the repo's case-insensitive uniqueness check; this gives the user a friendly inline error before the async call and avoids relying on `RepositoryError.message` strings as UI copy. The repo still acts as the source of truth — try/catch around `addCategory`/`editCategory` falls back to `error.message` if anything slips past the client guard.

## 2026-05-21 Task: dashboard-route (T19)
- Two distinct event-wiring patterns coexist cleanly under Svelte 5 runes: `ExpenseList` uses the callback-prop pattern (`onedit={openEdit}`) while `ExpenseFormModal` still uses `createEventDispatcher` and is wired with legacy `on:close={closeModal}` syntax. Both pass `svelte-check` 4.4.6 with zero warnings in this project — no migration needed for T19 to land.
- Dashboard `onMount` calls `refreshExpenses()` AND `refreshCategories()` even though `ExpenseList` and `ExpenseFormModal` also refresh on mount/open; the redundancy is intentional because `MonthlyBarChart` and `CategoryDoughnutChart` subscribe to the stores directly and would render empty on the first paint without a parent-level refresh.
- `editingExpense` is reset to `undefined` both when opening Add mode AND inside `closeModal` so a subsequent Add doesn't accidentally inherit the last-edited expense if the user opens → cancels edit → opens add.
- Charts are wrapped in matching card surfaces (`rounded-lg border ... bg-white dark:bg-[#111114]`) identical to the categories page form card; this keeps the dashboard visually consistent with the rest of the shell without introducing any new design tokens.
- `grid grid-cols-1 lg:grid-cols-2 gap-4` per the task spec stacks both charts on mobile/tablet and goes side-by-side only at `lg:` (1024px+); the list below uses the existing `ExpenseList` styling and needs no wrapper — placing it inside a card would double-border with the list's own border.
- The modal is rendered as a sibling AFTER the section, not nested inside `ExpenseList` and not inside the section, so the fixed-position backdrop never inherits any layout/stacking context from the dashboard grid.

## 2026-05-21 Task: e2e-playwright-suite (Final F1 fix)
- `playwright.config.ts` uses `webServer: { command: 'npm run build && npm run preview', port: 4173 }` with no `reuseExistingServer`; if the SvelteKit preview server is already bound to 4173 from a previous run, Playwright aborts with `http://localhost:4173 is already used`. Kill the lingering `node` PID on that port before re-running.
- `page.addInitScript` runs on EVERY navigation (including `page.reload()` and follow-up `page.goto`), so a naive `localStorage.setItem(LS_KEY, seed)` will silently wipe any test mutations made between navigations. Wrapping the setItem calls in `if (localStorage.getItem(key) === null)` keeps per-test isolation while preserving in-test state across reloads/navigations.
- Same applies to the `theme` key — the cascade test and the theme-persistence test both reload/navigate, so the seed helper must conditionally set theme as well.
- The mock store key `expense-tracker:store:v1` and the theme key `theme` are duplicated inline in `tests/helpers.ts` instead of imported from `$lib`, because Playwright spec files compile through `tsc` (not Vite) and don't get SvelteKit alias resolution; importing across the kit boundary would break the `webServer: build && preview` cycle.
- `seedLocalStorage` builds expenses with `isoDaysAgo()` (current-month dates) so the monthly bar chart's `last12MonthKeys()` window always contains the seed — date-based seeds with hardcoded ISO strings drift out of the chart's window over time and silently produce empty bars.
- Amount validation is best exercised by submitting `"0"` (or empty) rather than a non-numeric string: `<input type="number">` filters non-numeric keystrokes at the browser layer, so `fill('abc')` resolves to `""` and the assertion becomes ambiguous between "empty" and "rejected". `parseAmountInput('0')` returns `0` which the modal then rejects via the `parsedAmount <= 0` guard — unambiguous failure.
- For data-testid-only assertions, `page.getByTestId('expense-row').filter({ hasText: 'Coffee beans' })` is the idiomatic substitute for `page.getByText('Coffee beans')`: it scopes the text match to a known testid wrapper instead of leaking into role/label/text selectors that the plan guardrail forbids.
- `tests/` directory is picked up automatically by Playwright's default `testDir` (cwd) combined with the config's `testMatch: '**/*.e2e.{ts,js}'` glob; no `testDir` override needed.

## D1 — merchant name as primary list title (2026-05-21)

- **LS bump rationale**: Adding required `name: string` to `Expense` makes any persisted v1 payload structurally invalid (missing field on every row). Rather than write a one-shot migration that has to be deleted later, bumping the LS key from `expense-tracker:store:v1` → `v2` makes `loadFromStorage()` return `null` for stale keys, triggering `freshSeed()` on next read. Old v1 entries are simply ignored (no `removeItem` cleanup either — they're inert). The single LS key must stay in sync between `src/lib/repos/mockStore.ts` and `tests/helpers.ts` (the test helper duplicates the constant inline; this is documented above).
- **Row layout decision — date placement**: Date stays on the **first line beside the merchant name** (small, muted, right-aligned within the text column), not below. Rationale: keeps the visual hierarchy `merchant > category subtitle > note`, mirrors how Splitwise / Monzo render transaction rows, and avoids a third vertical line that would dominate the row on mobile. The colored category dot moves from "row-leading" to "inline prefix on the category subtitle" so the merchant name owns the primary baseline.
- **Validation rule for `name`**: required after `trim()`, max 80 chars after trim, inline error `data-testid="name-error"`. `maxlength="80"` on the input prevents the typical case at the browser layer; the JS `trim().length > 80` guard catches paste-with-whitespace edge cases. Trimmed value is what gets persisted via the payload, so leading/trailing spaces never enter the store. Error string: `"Enter a merchant name."` / `"Merchant name must be 80 characters or fewer."`.
- **Focus order**: initial focus moved from `amount-input` → `name-input` (first field). `nameFieldEl` replaces `amountFieldEl` as the `bind:this` target on modal open.
- **Repository update path**: `MockExpenseRepository.update()` rebuilds the row explicitly field-by-field (not spread) for transactional safety, so adding `name: patch.name ?? existing.name` is a one-line addition mirroring the existing pattern — no refactor.
- **Seed merchants chosen for category coverage**: every seeded category gets ≥2 recognizable real-world merchants spread across months 0–5, plus `Patreon` on the `Uncategorized` row to exercise the uncategorized-color path in the new subtitle layout. Existing `monthsAgo + day` realistic-date pattern preserved unchanged.
- **Test surface for D2/D3**: validation tests now `.fill('name-input', 'Test Merchant')` before exercising amount/category errors so each test isolates the error it claims to assert — necessary because the new `name-error` would otherwise also fire and muddy the assertion. The add-expense flow asserts on the merchant text (`'Blue Bottle Coffee'`) instead of the note text, since merchant is now the user-facing primary identity of a row.
