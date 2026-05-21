# Expense Tracker — Web UI

## TL;DR

> **Quick Summary**: Build a focused SvelteKit + TypeScript web UI for a minimal personal expense tracker — a dashboard with an expense list + Add/Edit modal + two monthly charts (bar trend + category doughnut), plus a `/categories` management page. All data goes through a repository interface; the implementation is a mock that mirrors the *future* HTTP API so the swap will be a one-line change.
>
> **Deliverables**:
> - Scaffolded SvelteKit project under `/Users/grant/dev/quid/webui` (TypeScript, Tailwind, Playwright)
> - Two routes: `/` (dashboard) and `/categories` (manage)
> - Expense CRUD via modal + inline row controls
> - Category CRUD (add / edit name & color / delete with cascade-to-Uncategorized)
> - Two Chart.js charts (12-month bar + category doughnut), both browser-only via `{#if browser}`
> - Light/dark theme toggle with FOUT-free initialization
> - Mobile-first responsive layout
> - Playwright E2E test suite (tests-after style) — one spec file per feature surface
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 6 waves + 1 final review wave
> **Critical Path**: T1 → T3 → T10 → T11/T12 → T14 → T15 → T19 → F1–F4 → user okay

---

## Context

### Original Request

> "I want to build a very very simple expense tracking web app. It shouldn't have any budgeting features, any multi-account features. The only thing in the app is the list of expenses, categorization of the expenses, and some charts to see how the expenses change over the course of months. So the app is going to consist of two parts: web UI and web API. For now I want to focus on web UI."

### Interview Summary

**Key Discussions**:
- **Framework**: SvelteKit + TypeScript (user choice; clean, focused, file-based routing fits two-route app)
- **Styling**: Tailwind CSS (no UI kit)
- **Charts**: Chart.js via `svelte-chartjs` (user choice)
- **Data source while API doesn't exist**: Mock data behind a swap-ready repository interface. The *future* backend API is the canonical source of truth; the mock mirrors that contract and uses `localStorage` only as a developer-convenience persistence layer.
- **Categories**: Predefined defaults + user can add/edit/delete custom. **Modeled as a separate resource with IDs** — `Expense.categoryId` references `Category { id, name, color }`. This shape mirrors the expected REST API.
- **Routes**: Two — `/` (dashboard = list + 2 charts + Add Expense button) and `/categories` (CRUD page).
- **Add/Edit/Delete expense UX**: Each list row has inline ✎ edit and 🗑 delete buttons. Edit and Add share a single modal component (accepts an optional `expense` prop). Delete uses inline row-level confirmation (not a JS `alert`, not a separate modal, not a toast library).
- **Category colors**: Auto-assigned by a deterministic function (id → HSL with fixed S/L tuned for both themes). **No hard cap on category count.** User may override the color via a color input on the category edit/create form.
- **Delete category in use**: Reassigns affected expenses to a special non-deletable `Uncategorized` category. Seed data includes `Uncategorized`. Mock repo enforces non-deletability.
- **Visual style**: Clean & minimal, light + dark mode, mobile-first responsive
- **Expense data model**: `{ id, amount, date, categoryId, note }` — single implicit currency, `date` as ISO 8601 `YYYY-MM-DD` string
- **Chart time range**: Trailing 12 months, fixed (no selector)
- **List behavior**: Sort by date (newest first), no filters / no search / no pagination
- **Tests**: Tests-after Playwright E2E only — no TDD, no unit tests — plus per-task agent-executed Playwright QA scenarios

**Research Findings**:
- Workspace is greenfield (empty `/Users/grant/dev/quid/webui` directory) — no patterns to match
- SvelteKit + Chart.js SSR gotcha pre-empted: use `{#if browser}` guards around chart components (do not disable SSR for the whole route)
- Tailwind dark-mode FOUT pre-empted: inline `<script>` in `app.html` reads `localStorage.theme` and sets the `dark` class on `<html>` *before* paint

### Metis Review

**Identified Gaps (all addressed)**:
- Edit/delete expense UX undefined → resolved: shared modal + inline icons + inline confirm
- Delete-category-in-use undefined → resolved: reassign-to-Uncategorized cascade
- Category color strategy undefined → resolved: deterministic hash + user override
- Category-name duplication edge case → default applied: category names are case-insensitively unique, because duplicate names make the expense-category dropdown and chart legend ambiguous. This is an ambiguity default from Metis's edge-case review, not an extra feature.
- Chart.js SSR concerns → addressed: `{#if browser}` guards mandated in guardrails
- Dark-mode FOUT → addressed: inline script in `app.html` mandated
- Empty state, zero-month chart bars, date format, amount precision → all called out in guardrails and acceptance criteria

---

## Work Objectives

### Core Objective
Deliver a working SvelteKit web UI that lets a single user record, list, categorize, and visually trend their personal expenses — backed by a repository interface that the future HTTP API will plug into without changing UI code.

### Concrete Deliverables
- `/Users/grant/dev/quid/webui/` SvelteKit project, runnable with `npm run dev`
- Route `/` rendering: top nav (with theme toggle), Add Expense button, expense list, monthly bar chart, category doughnut chart, empty state when no expenses
- Route `/categories` rendering: list of categories (default + custom), add form, edit each row, delete with cascade behavior, color override input
- Repository module: `interface ExpenseRepository`, `interface CategoryRepository`, `MockExpenseRepository`, `MockCategoryRepository`, shared `mockStore` backing them
- Domain types module: `Expense`, `Category`, `UNCATEGORIZED_ID` constant
- Two chart components rendering Chart.js canvases gated by `{#if browser}`
- Playwright E2E suite covering: dashboard load, add expense, edit expense, delete expense, theme toggle persistence, empty state, category add/edit/delete, cascade behavior, form validation
- All implementation conforms to every guardrail under "Must NOT Have"

### Definition of Done
- [ ] `npm run dev` starts the app with no console errors on either route
- [ ] `npm run build` completes without errors
- [ ] `npx playwright test` passes (all specs green)
- [ ] All "Must Have" items are verifiable via tool-driven QA scenarios
- [ ] All "Must NOT Have" items are absent from the codebase (verified by `grep`/`ast-grep` searches in F1)
- [ ] Final Verification Wave F1–F4 all return APPROVE
- [ ] User gives explicit "okay" after seeing F1–F4 results

### Must Have
- Two routes only: `/` and `/categories`
- Dashboard composes list + 2 charts + Add Expense launcher in a single page
- Single shared modal component for both Add and Edit expense (driven by an optional `expense` prop)
- Inline ✎ and 🗑 controls on every expense row
- Inline (in-row) delete confirmation pattern — no JS `alert`, no toast library, no separate modal
- Deterministic category color from id-hash; user override via color input persisted with the category
- `Uncategorized` category is seeded, deterministic id (`UNCATEGORIZED_ID`), neutral color, **NOT deletable** (repo enforces; UI hides delete button)
- Deleting any other category cascades by reassigning affected expenses' `categoryId` to `UNCATEGORIZED_ID` in a single transactional update of the mock store
- Category names are case-insensitively unique after trimming whitespace; duplicate names are rejected with inline validation errors to avoid ambiguous dropdown choices and chart legends
- Monthly bar chart always has exactly 12 bars (trailing 12 months, zero-filled for empty months)
- Category doughnut renders one segment per category present in the current expense set
- Theme toggle persists to `localStorage` under the key `theme` (`"light"` or `"dark"`)
- Inline FOUT-prevention `<script>` in `app.html` sets `dark` class on `<html>` synchronously from `localStorage.theme` before first paint
- All Chart.js components are wrapped in `{#if browser}` (using `$app/environment`)
- `Chart.register(...registerables)` called exactly once in `src/lib/chart/chartSetup.ts`, imported by every chart component
- Chart containers have explicit Tailwind height (`h-64` or similar) — Chart.js collapses without it
- Amount displayed with exactly 2 decimal places via `Intl.NumberFormat`
- Empty-state component shown when expense list is empty
- All Playwright assertions use `data-testid` selectors only
- Mobile-first responsive: nav collapses sensibly on `< 640px`, charts stack vertically, modal becomes full-screen on small screens
- `ExpenseRepository.list()` signature accepts optional `{ limit?: number; offset?: number }` (ignored by mock) to future-proof the API contract
- Mock repos return *deep copies* of stored objects so the UI can't accidentally mutate the store

### Must NOT Have (Guardrails)

> These are non-negotiable. F1 (Plan Compliance Audit) will reject the work if any of these are violated.

- **NO** `<Button>`, `<Input>`, `<Modal>`, or `<Card>` wrapper components (use styled HTML elements directly; exception only if the same pattern is duplicated 4+ times identically)
- **NO** form validation library (zod, superforms, vee-validate) — native HTML5 + one `validate()` function per form
- **NO** state-management library (Zustand-port, etc.) — plain Svelte `writable` stores only
- **NO** derived-store proliferation — a derived store is justified only if its value is read in 3+ places
- **NO** `@apply` directive in CSS, *except* for the dark-mode body background line
- **NO** toast/notification library — inline error/success messages only
- **NO** pagination, filtering, searching, sorting controls on the expense list
- **NO** date-range selector on the charts (trailing 12 months is fixed)
- **NO** export (CSV/PDF), import, or bulk-action features
- **NO** authentication, accounts, "current user" concept
- **NO** budgeting, spending limits, alerts
- **NO** animations beyond Tailwind's built-in `transition-*`/`duration-*` utilities
- **NO** settings drawer or `/settings` route — theme toggle lives in the nav
- **NO** more than 2 charts — monthly bar + category doughnut, that's it
- **NO** `<ThemeProvider>` component or theme context abstraction
- **NO** `+page.server.js` files (all data is client-side via mock repo + localStorage)
- **NO** simulated network latency, error states, retries, or spinners in the mock repo
- **NO** generic `BaseRepository<T>` abstraction or CRUD mixin
- **NO** speculative repo methods (no `findByDateRange`, `getStats`, etc.) — only methods the UI actually calls
- **NO** icon library (lucide, heroicons-svelte, etc.) — use Unicode glyphs (`✎`, `🗑`) or inline SVG strings
- **NO** Storybook, Histoire, or any component playground
- **NO** SSR error suppression hacks — if SSR breaks, fix with `{#if browser}`, not with `export const ssr = false`
- **NO** `as any`, `@ts-ignore`, `@ts-expect-error` in shipped code
- **NO** `console.log` in shipped code (debug logs must be removed before commit)
- **NO** commented-out code blocks left behind

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No acceptance criteria may require "user manually tests/confirms".

### Test Decision
- **Infrastructure exists**: NO (greenfield)
- **Automated tests**: **Tests-after, Playwright E2E only**
- **Framework**: Playwright (set up in T1)
- **Rationale**: Writing E2E tests before any UI exists is ergonomically wasteful for a greenfield UI; no unit-test pyramid for a scope this small.
- **TDD**: NOT used. Each task implements first; the same task adds its Playwright spec coverage as part of its acceptance criteria.

### QA Policy

Every task includes agent-executed QA scenarios (see template inside each TODO). Evidence is saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI tasks** → use the `playwright` skill: launch dev server, navigate, interact with elements via `data-testid` selectors, capture screenshots, assert DOM state.
- **Pure-module tasks** (types, utilities, repos) → use `Bash` (e.g., `bun -e "import { ... } ..."` or a small `tsx` script) to import the module, exercise its surface, and assert outputs.
- **Build/scaffolding tasks** → use `Bash` to run the relevant CLI (`npm run dev`, `npm run build`, `npx playwright --version`), capture stdout/stderr, assert exit codes.

Each scenario must include **at least one happy path and at least one negative/edge case**.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (start immediately — scaffolding bedrock; ONLY 1 task because everything else needs it):
└── T1: Scaffold SvelteKit project (TS + Tailwind + Playwright + path aliases + base CSS)

Wave 2 (after Wave 1 — 8 parallel foundation tasks, NO inter-deps within wave):
├── T2: Domain types (Expense, Category, UNCATEGORIZED_ID)
├── T3: Repository interfaces (ExpenseRepository, CategoryRepository, error types)
├── T4: Color hash utility (id → HSL with light/dark tuning)
├── T5: Date utilities (12-month window, formatting)
├── T6: Money formatter (Intl.NumberFormat 2dp)
├── T7: Chart.js setup module (Chart.register call, shared imports)
├── T8: Tailwind dark-mode config + app.html FOUT script + global.css
└── T9: Default category seed data module

Wave 3 (after Wave 2 — 3 tasks, sequential WITHIN the wave: T10 then T11+T12 parallel):
├── T10: Mock data store (in-memory + localStorage persistence + seeding) [needs T2, T9]
├── T11: MockExpenseRepository (needs T3, T10)
└── T12: MockCategoryRepository (needs T3, T10) — implements cascade-to-Uncategorized

Wave 4 (after Wave 3 — 4 parallel tasks):
├── T13: Root +layout.svelte (top nav + theme toggle + dark-mode JS hookup) [needs T8]
├── T14: Svelte writable stores (expensesStore, categoriesStore, themeStore) [needs T11, T12]
├── T15: Expense list component (rows + empty state + inline delete-confirm) [needs T14, T4, T6]
└── T16: Expense Add/Edit modal component (form + validation + shared by both flows) [needs T14, T6]

Wave 5 (after Wave 4 — 3 parallel tasks: charts + independent categories route):
├── T17: MonthlyBarChart component ({#if browser}) [needs T14, T5, T7]
├── T18: CategoryDoughnutChart component ({#if browser}) [needs T14, T4, T7]
└── T20: Categories route src/routes/categories/+page.svelte (list + form + color override + cascade UX) [needs T13, T14, T4]

Wave 6 (after Wave 5 — final dashboard composition):
└── T19: Dashboard route src/routes/+page.svelte (compose T15, T16, T17, T18) [needs T15, T16, T17, T18]

Wave FINAL (after ALL implementation tasks — 4 parallel reviews, then user okay):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA via Playwright (unspecified-high + playwright skill)
└── F4: Scope fidelity check (deep)
→ Present consolidated results → wait for explicit user "okay"

Critical Path: T1 → T3 → T10 → T11/T12 → T14 → T15 → T19 → F1–F4 → user okay
Max Concurrent: 8 (Wave 2)
Total Tasks: 20 implementation + 4 final review = 24
```

> **Note on Wave 1 and Wave 6 having few tasks**: Wave 1 is a single task because every subsequent task imports from a directory tree that doesn't exist yet — splitting would create file-conflict races on `package.json`. Wave 6 has only 1 task because the dashboard composition is the final integration point for the list, modal, and both charts; running it earlier would force chart stubs or rework. Both are intentional, dependency-forced exceptions rather than under-splitting.

### Dependency Matrix

- **T1**: deps `—` ; blocks `T2–T9` (everything)
- **T2**: deps `T1` ; blocks `T10, T15, T16, T17, T18, T20`
- **T3**: deps `T1, T2` ; blocks `T11, T12, T14`
- **T4**: deps `T1` ; blocks `T15, T18, T20`
- **T5**: deps `T1` ; blocks `T17`
- **T6**: deps `T1` ; blocks `T15, T16`
- **T7**: deps `T1` ; blocks `T17, T18`
- **T8**: deps `T1` ; blocks `T13`
- **T9**: deps `T1, T2` ; blocks `T10`
- **T10**: deps `T1, T2, T9` ; blocks `T11, T12`
- **T11**: deps `T1, T3, T10` ; blocks `T14`
- **T12**: deps `T1, T3, T10` ; blocks `T14`
- **T13**: deps `T1, T8` ; blocks `T19, T20`
- **T14**: deps `T1, T11, T12` ; blocks `T15, T16, T17, T18, T20`
- **T15**: deps `T1, T2, T4, T6, T14` ; blocks `T19`
- **T16**: deps `T1, T2, T6, T14` ; blocks `T19`
- **T17**: deps `T1, T2, T5, T7, T14` ; blocks `T19`
- **T18**: deps `T1, T2, T4, T7, T14` ; blocks `T19`
- **T19**: deps `T13, T15, T16, T17, T18` ; blocks `F1–F4`
- **T20**: deps `T2, T4, T13, T14` ; blocks `F1–F4`
- **F1–F4**: deps `T19, T20` ; blocks final user-okay step

### Agent Dispatch Summary

- **Wave 1**: 1 task → T1 → `quick` (mechanical scaffolding)
- **Wave 2**: 8 tasks → T2–T9 → all `quick` (small focused foundation files)
- **Wave 3**: 3 tasks → T10 → `unspecified-high`, T11–T12 → `unspecified-high` (cascade logic is non-trivial)
- **Wave 4**: 4 tasks → T13 → `visual-engineering`, T14 → `quick`, T15–T16 → `visual-engineering`
- **Wave 5**: 3 tasks → T17–T18 + T20 → `visual-engineering`
- **Wave 6**: 1 task → T19 → `visual-engineering` (dependency-forced final composition)
- **Wave FINAL**: 4 tasks → F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high` (+ `playwright` skill), F4 → `deep`

---

## TODOs

> Every task includes: What to do · Must NOT do · Recommended Agent Profile · Parallelization · References · Acceptance Criteria · QA Scenarios · Commit.

- [x] 1. **Scaffold SvelteKit project (TS + Tailwind + Playwright + base config)**

  **What to do**:
  - From `/Users/grant/dev/quid/webui`, run `npx sv create .` (or the current canonical SvelteKit init command) selecting: **Skeleton project**, **TypeScript**, **Add Prettier**, **Add ESLint**, **Add Playwright**, **Add Tailwind CSS**.
  - If `sv create` is unavailable, fall back to `npm create svelte@latest .` with the equivalent options.
  - Confirm/install: `@sveltejs/kit`, `svelte`, `typescript`, `vite`, `tailwindcss`, `@tailwindcss/typography` (only if needed for prose), `autoprefixer`, `postcss`, `@playwright/test`, `svelte-chartjs`, `chart.js`.
  - Configure `tailwind.config.js`:
    - `content: ['./src/**/*.{html,js,svelte,ts}']`
    - `darkMode: 'class'` (NOT `'media'` — required for the toggle)
  - Configure `svelte.config.js` for `@sveltejs/adapter-auto` (default).
  - Configure TypeScript path aliases in `tsconfig.json`: `"$lib/*": ["src/lib/*"]` (SvelteKit default), plus `"$repos/*": ["src/lib/repos/*"]`, `"$components/*": ["src/lib/components/*"]`, `"$types/*": ["src/lib/types/*"]`, `"$utils/*": ["src/lib/utils/*"]`.
  - Create empty placeholder directories so subsequent waves don't fight over `src/lib/` creation: `src/lib/types/`, `src/lib/utils/`, `src/lib/repos/`, `src/lib/components/`, `src/lib/stores/`, `src/lib/chart/`.
  - Add a `.gitignore` that excludes `node_modules/`, `.svelte-kit/`, `build/`, `playwright-report/`, `test-results/`, `.omo/evidence/`.
  - Initialize git: `git init && git add -A && git commit -m "chore: initial sveltekit scaffold"`.

  **Must NOT do**:
  - Do NOT install a UI kit (no shadcn-svelte, no daisyui, no skeleton, no flowbite-svelte).
  - Do NOT install any state-management library.
  - Do NOT install any form validation library (no zod, no superforms).
  - Do NOT install an icon library.
  - Do NOT add `+page.server.ts` anywhere.
  - Do NOT create a Storybook/Histoire config.
  - Do NOT add a `README.md` populated with marketing copy — a one-line `# Expense Tracker Web UI` is sufficient if SvelteKit's template didn't already create one.

  **Recommended Agent Profile**:
  - **Category**: `quick` — purely mechanical CLI + config edits.
    - Reason: No decisions, no logic. Run installer, paste config.
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**: `customize-opencode` (we are configuring a SvelteKit app, not opencode itself).

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (alone)
  - **Blocks**: T2–T9 (every subsequent task)
  - **Blocked By**: None — can start immediately

  **References**:

  **Pattern References**: None (greenfield).

  **External References**:
  - SvelteKit getting started: `https://svelte.dev/docs/kit/creating-a-project` — current canonical scaffolding command, options menu walkthrough.
  - Tailwind dark-mode docs: `https://tailwindcss.com/docs/dark-mode` — confirm `darkMode: 'class'` is the current API key.
  - Playwright with SvelteKit: `https://playwright.dev/docs/intro` and SvelteKit's bundled `vite.config.ts` notes about test ports — confirm default `webServer.command: 'npm run build && npm run preview'` or `'npm run dev'` works.
  - `svelte-chartjs`: `https://github.com/SauravKanchan/svelte-chartjs` — verify it supports Svelte 5 if scaffolded project is Svelte 5; if not, prefer the Svelte 4 path or `svelte-chartjs-2`.

  **WHY each reference matters**:
  - SvelteKit docs may have renamed the create command since training — always defer to the current docs.
  - Tailwind v4 changed config semantics in some areas — verify `darkMode: 'class'` still works as expected.

  **Acceptance Criteria**:

  - [ ] `ls webui/` shows `package.json`, `svelte.config.js`, `tailwind.config.{js,ts}`, `tsconfig.json`, `playwright.config.ts`, `src/`, `static/`
  - [ ] `cat webui/package.json | jq '.dependencies, .devDependencies'` includes svelte, @sveltejs/kit, tailwindcss, @playwright/test, chart.js, svelte-chartjs
  - [ ] `cat webui/tailwind.config.{js,ts}` contains `darkMode: 'class'`
  - [ ] All six empty placeholder directories exist under `src/lib/`
  - [ ] `cd webui && npm run build` exits 0
  - [ ] `cd webui && npx tsc --noEmit` exits 0
  - [ ] `cd webui && git log --oneline` shows the initial commit

  **QA Scenarios**:

  ```
  Scenario: Scaffold completes and dev server starts
    Tool: Bash
    Preconditions: /Users/grant/dev/quid/webui is empty
    Steps:
      1. cd /Users/grant/dev/quid/webui && [scaffold command per references]
      2. Apply config edits (tailwind darkMode, tsconfig aliases, placeholder dirs)
      3. npm install (if not auto-run)
      4. npm run dev &  (start dev server in background)
      5. sleep 5
      6. curl -sf http://localhost:5173/ -o .omo/evidence/task-1-dev-server-root.html
      7. kill %1
    Expected Result: HTTP 200 from /, HTML body contains SvelteKit default content, no console errors in stderr
    Failure Indicators: non-zero exit on curl; stderr contains "Error"; missing file in src/
    Evidence: .omo/evidence/task-1-dev-server-root.html, .omo/evidence/task-1-npm-build.txt

  Scenario: Build succeeds (negative — must fail loudly on misconfig)
    Tool: Bash
    Preconditions: scaffold complete
    Steps:
      1. cd /Users/grant/dev/quid/webui && npm run build 2>&1 | tee .omo/evidence/task-1-npm-build.txt
      2. echo "exit=$?" >> .omo/evidence/task-1-npm-build.txt
    Expected Result: "exit=0" in evidence file; no "Error" lines preceding it; build output mentions client+server bundle paths.
    Failure Indicators: exit != 0; SSR-import warnings about chart.js (shouldn't appear yet since chart.js isn't imported).
    Evidence: .omo/evidence/task-1-npm-build.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-1-dev-server-root.html`
  - [ ] `task-1-npm-build.txt`

  **Commit**: YES — `chore(scaffold): sveltekit + ts + tailwind + playwright`. Files: every scaffolded file. Pre-commit: `npx tsc --noEmit && npm run build`.

- [x] 2. **Domain types** — `src/lib/types/domain.ts`

  **What to do**:
  - Create `src/lib/types/domain.ts` exporting:
    - `export interface Expense { id: string; amount: number; date: string; /* ISO 8601 YYYY-MM-DD */ categoryId: string; note: string; }`
    - `export interface Category { id: string; name: string; color: string; /* CSS hex like '#3b82f6' */ }`
    - `export const UNCATEGORIZED_ID = 'uncategorized' as const;`
    - `export type CategoryId = string & { readonly __brand?: 'CategoryId' };` (optional brand; if it feels too much, omit — the user said "very very simple")
  - Add a top-of-file comment block documenting the API contract assumptions: `id` is a string (UUID-shaped from mock; backend may use any string), `date` is ISO `YYYY-MM-DD`, `amount` is a positive number (validation enforced in form layer, not in the type).
  - Re-export from `src/lib/types/index.ts` for ergonomic imports: `export * from './domain';`

  **Must NOT do**:
  - Do NOT add speculative fields (`currency`, `paymentMethod`, `tags`, `createdAt`, `updatedAt`).
  - Do NOT use enums for category — categories are user-defined values from the categories resource.
  - Do NOT export classes — types/interfaces only.

  **Recommended Agent Profile**:
  - **Category**: `quick` — small focused type module.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T10, T15, T16, T17, T18, T20
  - **Blocked By**: T1

  **References**:
  - The Metis directive section in this plan ("Assumptions Needing Validation") documents the rationale for `id: string`, `date: string`, `amount: number`.
  - TypeScript brand types: `https://www.typescriptlang.org/docs/handbook/advanced-types.html#intersection-types` — for the optional `CategoryId` brand.

  **Acceptance Criteria**:
  - [ ] File exists at `src/lib/types/domain.ts` with all four exports
  - [ ] `src/lib/types/index.ts` re-exports everything
  - [ ] `npx tsc --noEmit` passes
  - [ ] Top-of-file JSDoc comment documents date format, amount sign, id shape

  **QA Scenarios**:

  ```
  Scenario: Types import and satisfy the interface
    Tool: Bash
    Preconditions: T2 implementation complete
    Steps:
      1. cd /Users/grant/dev/quid/webui
      2. Write a tiny script .omo/evidence/task-2-typecheck.ts that:
           import type { Expense, Category } from './src/lib/types';
           import { UNCATEGORIZED_ID } from './src/lib/types';
           const e: Expense = { id: 'x', amount: 1.5, date: '2026-01-01', categoryId: UNCATEGORIZED_ID, note: '' };
           const c: Category = { id: 'a', name: 'A', color: '#000000' };
           console.log(JSON.stringify({ e, c, UNCATEGORIZED_ID }));
      3. npx tsc --noEmit --project tsconfig.json .omo/evidence/task-2-typecheck.ts 2>&1 | tee .omo/evidence/task-2-typecheck.txt
    Expected Result: empty tsc output (success); JSON log of the constructed objects
    Failure Indicators: TS errors; UNCATEGORIZED_ID missing
    Evidence: .omo/evidence/task-2-typecheck.txt

  Scenario: No speculative fields snuck in (negative)
    Tool: Bash
    Steps:
      1. grep -E "(currency|paymentMethod|tags|createdAt|updatedAt)" src/lib/types/domain.ts | tee .omo/evidence/task-2-no-speculative.txt
    Expected Result: empty file (no matches)
    Failure Indicators: any matches
    Evidence: .omo/evidence/task-2-no-speculative.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-2-typecheck.txt`
  - [ ] `task-2-no-speculative.txt`

  **Commit**: YES — `feat(types): expense + category domain types`. Files: `src/lib/types/domain.ts`, `src/lib/types/index.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 3. **Repository interfaces** — `src/lib/repos/types.ts`

  **What to do**:
  - Create `src/lib/repos/types.ts` exporting:
    ```ts
    import type { Expense, Category } from '$types';

    export interface ListExpensesQuery { limit?: number; offset?: number; }
    export interface ExpenseRepository {
      list(query?: ListExpensesQuery): Promise<Expense[]>;
      create(input: Omit<Expense, 'id'>): Promise<Expense>;
      update(id: string, patch: Partial<Omit<Expense, 'id'>>): Promise<Expense>;
      delete(id: string): Promise<void>;
    }
    export interface CategoryRepository {
      list(): Promise<Category[]>;
      create(input: Omit<Category, 'id'>): Promise<Category>;
      update(id: string, patch: Partial<Omit<Category, 'id'>>): Promise<Category>;
      delete(id: string): Promise<void>; // throws RepositoryError if id === UNCATEGORIZED_ID
    }
    export class RepositoryError extends Error { constructor(public code: 'NOT_FOUND'|'IMMUTABLE'|'VALIDATION', message: string) { super(message); this.name = 'RepositoryError'; } }
    ```
  - Re-export from `src/lib/repos/index.ts`.
  - Add JSDoc above each interface explaining that mutations return the resulting object (for HTTP adapter compatibility) and that `list()` accepts an optional `query` to future-proof against pagination.

  **Must NOT do**:
  - Do NOT define a `BaseRepository<T>` generic.
  - Do NOT add speculative methods (`findByDateRange`, `getStats`, `bulkCreate`, etc.).
  - Do NOT add a streaming/observable variant — Promise-based only.
  - Do NOT include AbortSignal in any signature (over-engineering for this scope).

  **Recommended Agent Profile**:
  - **Category**: `quick` — interface definition only.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T11, T12, T14
  - **Blocked By**: T1, T2

  **References**:
  - Metis directive: methods are exactly what the UI calls — no speculation.
  - Future API contract: REST-shaped (`GET /expenses`, `POST /expenses`, `PATCH /expenses/:id`, `DELETE /expenses/:id`) — these signatures map 1:1.

  **Acceptance Criteria**:
  - [ ] File exists with all 4 interface exports + `RepositoryError`
  - [ ] `src/lib/repos/index.ts` re-exports
  - [ ] `npx tsc --noEmit` passes
  - [ ] `grep -E "(BaseRepository|findBy|bulkCreate|AbortSignal|Observable)" src/lib/repos/types.ts` returns no matches

  **QA Scenarios**:
  ```
  Scenario: Interfaces compile and shape matches future REST API
    Tool: Bash
    Steps:
      1. Write evidence script that imports both interfaces and creates a no-op class implementing each (declaration only, body returns Promise.reject)
      2. npx tsc --noEmit on the script
      3. Save tsc output to .omo/evidence/task-3-interfaces.txt
    Expected Result: clean tsc output
    Failure Indicators: shape mismatch errors
    Evidence: .omo/evidence/task-3-interfaces.txt

  Scenario: No forbidden patterns
    Tool: Bash
    Steps:
      1. grep -nE "(BaseRepository|findBy|bulkCreate|AbortSignal|Observable|stream)" src/lib/repos/types.ts > .omo/evidence/task-3-no-forbidden.txt || true
      2. test ! -s .omo/evidence/task-3-no-forbidden.txt && echo "OK" >> .omo/evidence/task-3-no-forbidden.txt
    Expected Result: file ends with "OK"
    Evidence: .omo/evidence/task-3-no-forbidden.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-3-interfaces.txt`
  - [ ] `task-3-no-forbidden.txt`

  **Commit**: YES — `feat(repos): repository interfaces + error type`. Files: `src/lib/repos/types.ts`, `src/lib/repos/index.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 4. **Category color hash utility** — `src/lib/utils/categoryColor.ts`

  **What to do**:
  - Create `src/lib/utils/categoryColor.ts` exporting:
    ```ts
    /** Deterministic id → hex color. Hue chosen via simple string hash; S/L tuned to be legible on both light and dark backgrounds. */
    export function colorForCategoryId(id: string): string {
      let h = 0;
      for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
      const hue = h % 360;
      // S=68%, L=52% chosen empirically to remain legible on white and on near-black.
      return hslToHex(hue, 68, 52);
    }
    export function hslToHex(h: number, s: number, l: number): string { /* standard conversion */ }
    /** Special color for the Uncategorized category — neutral gray, theme-neutral. */
    export const UNCATEGORIZED_COLOR = '#9ca3af'; // tailwind gray-400
    ```
  - The function must be **pure and deterministic** — same input always returns same output.
  - User-overridden colors are stored on the `Category.color` field; `colorForCategoryId` is used only as a default when creating a new category.

  **Must NOT do**:
  - Do NOT use `Math.random()` anywhere.
  - Do NOT depend on `window` or any browser API.
  - Do NOT cap at 12 colors via modulo or palette lookup — full 360° hue space.
  - Do NOT import from any external package.

  **Recommended Agent Profile**:
  - **Category**: `quick` — pure function, < 30 LOC.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T15, T18, T20
  - **Blocked By**: T1

  **References**:
  - HSL→RGB algorithm: `https://en.wikipedia.org/wiki/HSL_and_HSV#Converting_to_RGB` — implement directly, no library.
  - Metis directive: "deterministic, no 12-color cap, user override allowed".

  **Acceptance Criteria**:
  - [ ] File exists with `colorForCategoryId`, `hslToHex`, `UNCATEGORIZED_COLOR`
  - [ ] `colorForCategoryId('foo') === colorForCategoryId('foo')` (determinism)
  - [ ] `colorForCategoryId('a')` and `colorForCategoryId('b')` produce different hexes (collision unlikely)
  - [ ] Output matches `/^#[0-9a-f]{6}$/i` for any non-empty input

  **QA Scenarios**:
  ```
  Scenario: Determinism + format
    Tool: Bash
    Steps:
      1. Write evidence script with several test inputs ('a','b','foo','uncategorized','💰','x'.repeat(100))
      2. Call colorForCategoryId twice for each; assert equality and regex match
      3. Save output to .omo/evidence/task-4-determinism.json
    Expected Result: all assertions pass; ≥4 unique hues among 6 inputs
    Failure Indicators: any assertion fail; only 1 unique color
    Evidence: .omo/evidence/task-4-determinism.json

  Scenario: No Math.random / no browser deps (negative)
    Tool: Bash
    Steps:
      1. grep -nE "(Math\.random|window\.|document\.)" src/lib/utils/categoryColor.ts > .omo/evidence/task-4-no-impurity.txt || true
      2. test ! -s .omo/evidence/task-4-no-impurity.txt && echo "OK" >> .omo/evidence/task-4-no-impurity.txt
    Expected Result: file ends with "OK"
    Evidence: .omo/evidence/task-4-no-impurity.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-4-determinism.json`
  - [ ] `task-4-no-impurity.txt`

  **Commit**: YES — `feat(utils): deterministic category color hash`. Files: `src/lib/utils/categoryColor.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 5. **Date utilities** — `src/lib/utils/dates.ts`

  **What to do**:
  - Create `src/lib/utils/dates.ts` exporting:
    - `monthKey(date: string | Date): string` — returns `YYYY-MM` (e.g., `'2026-05'`). Accepts ISO `YYYY-MM-DD` string or Date.
    - `last12MonthKeys(reference?: Date): string[]` — returns exactly 12 `YYYY-MM` keys in ascending order, ending with the month of `reference` (default: now). E.g., `['2025-06', ..., '2026-05']`.
    - `formatMonthLabel(key: string): string` — `'2026-05'` → `'May 2026'` via `Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' })`.
    - `todayIso(): string` — `YYYY-MM-DD` for current local date, suitable as `<input type="date">` default value.
  - All functions are pure. Use `Date.UTC` semantics carefully when constructing month windows — comment any timezone assumptions.

  **Must NOT do**:
  - Do NOT import `dayjs`, `date-fns`, `luxon`, `moment`, or any other date library.
  - Do NOT mutate Date objects.
  - Do NOT make `last12MonthKeys` configurable beyond an optional reference Date.

  **Recommended Agent Profile**:
  - **Category**: `quick` — pure functions, ~50 LOC.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T17
  - **Blocked By**: T1

  **References**:
  - `Intl.DateTimeFormat` MDN: `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat`
  - Metis directive: "All 12 months always present in chart data (zero-fill empty months)" — this is the function that enables zero-fill.

  **Acceptance Criteria**:
  - [ ] All four functions exported
  - [ ] `last12MonthKeys(new Date('2026-05-15'))[11] === '2026-05'`
  - [ ] `last12MonthKeys(new Date('2026-05-15'))[0] === '2025-06'`
  - [ ] `last12MonthKeys(...).length === 12` for any reference
  - [ ] `monthKey('2026-05-15') === '2026-05'`
  - [ ] `formatMonthLabel('2026-05')` includes `'May'` and `'2026'`
  - [ ] `todayIso()` matches `/^\d{4}-\d{2}-\d{2}$/`

  **QA Scenarios**:
  ```
  Scenario: Window math correctness (year boundary)
    Tool: Bash
    Steps:
      1. Evidence script tests last12MonthKeys with references at Jan, Dec, Feb-29-leap, and 'today'.
      2. Assert each call returns exactly 12 keys, ascending, no duplicates, last entry matches the reference month.
      3. Save assertions log to .omo/evidence/task-5-window-math.txt
    Expected Result: all assertions pass
    Failure Indicators: 13 entries; duplicate keys; descending order
    Evidence: .omo/evidence/task-5-window-math.txt

  Scenario: No date library imports (negative)
    Tool: Bash
    Steps:
      1. grep -nE "from '(dayjs|date-fns|luxon|moment)'" src/lib/utils/dates.ts > .omo/evidence/task-5-no-libs.txt || true
      2. test ! -s .omo/evidence/task-5-no-libs.txt && echo "OK" >> .omo/evidence/task-5-no-libs.txt
    Expected Result: "OK"
    Evidence: .omo/evidence/task-5-no-libs.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-5-window-math.txt`
  - [ ] `task-5-no-libs.txt`

  **Commit**: YES — `feat(utils): date window + month-key helpers`. Files: `src/lib/utils/dates.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 6. **Money formatter** — `src/lib/utils/money.ts`

  **What to do**:
  - Create `src/lib/utils/money.ts` exporting:
    - `formatAmount(amount: number): string` — `Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)`. Uses runtime default locale.
    - `parseAmountInput(raw: string): number | null` — strips whitespace, accepts `"42"`, `"42.5"`, `"42.50"`; rejects negatives, NaN, empty. Returns `null` on invalid (so the form layer can render an inline error).
  - Both functions pure. No currency symbol prefix — caller decides if/how to display one (the user's app is single-implicit-currency with no symbol).

  **Must NOT do**:
  - Do NOT inject a currency code or symbol — formatting is number-only.
  - Do NOT round; use `Intl.NumberFormat`'s native rounding behavior.
  - Do NOT throw on invalid input — return `null`.
  - Do NOT use `parseFloat` directly (it accepts garbage like `"42abc"`).

  **Recommended Agent Profile**:
  - **Category**: `quick` — pure formatter, < 40 LOC.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T15, T16
  - **Blocked By**: T1

  **References**:
  - `Intl.NumberFormat` MDN: `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat`

  **Acceptance Criteria**:
  - [ ] `formatAmount(42)` returns `'42.00'` (en-US default) — exact match
  - [ ] `formatAmount(42.999)` returns `'43.00'` (banker's/half-to-even rounding via Intl)
  - [ ] `parseAmountInput('42.50') === 42.5`
  - [ ] `parseAmountInput('-5') === null`
  - [ ] `parseAmountInput('abc') === null`
  - [ ] `parseAmountInput('') === null`
  - [ ] `parseAmountInput('  12.3  ') === 12.3`

  **QA Scenarios**:
  ```
  Scenario: Round-trip and rejection table
    Tool: Bash
    Steps:
      1. Evidence script enumerates 12 inputs (valid + invalid) and prints `{ input, parsed, formatted }`
      2. Assert each pair matches the expected table inline
      3. Save to .omo/evidence/task-6-money-table.json
    Expected Result: all 12 assertions pass
    Failure Indicators: any negative number parsed as non-null; any "abc" parsed as a number
    Evidence: .omo/evidence/task-6-money-table.json

  Scenario: No currency symbol leakage
    Tool: Bash
    Steps:
      1. grep -nE "(currency|USD|EUR|\\$|€)" src/lib/utils/money.ts > .omo/evidence/task-6-no-currency.txt || true
      2. test ! -s .omo/evidence/task-6-no-currency.txt && echo "OK" >> .omo/evidence/task-6-no-currency.txt
    Expected Result: "OK"
    Evidence: .omo/evidence/task-6-no-currency.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-6-money-table.json`
  - [ ] `task-6-no-currency.txt`

  **Commit**: YES — `feat(utils): 2dp amount formatter + safe parser`. Files: `src/lib/utils/money.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 7. **Chart.js setup module** — `src/lib/chart/chartSetup.ts`

  **What to do**:
  - Create `src/lib/chart/chartSetup.ts`:
    ```ts
    import { Chart, registerables } from 'chart.js';
    let registered = false;
    export function ensureChartJsRegistered() {
      if (registered) return;
      Chart.register(...registerables);
      registered = true;
    }
    ```
  - The function is called exactly once per chart component's `onMount` (idempotent so order doesn't matter).
  - Also export shared chart options helpers — e.g., a function `chartThemeColors(isDark: boolean)` returning `{ tick: string; grid: string; legend: string; }` hex values for axis ticks, gridlines, and legend text. These are NOT CSS-driven (Chart.js doesn't read CSS) — they're explicit hex codes that match the Tailwind palette: light mode uses `#374151` (gray-700) for text and `#e5e7eb` (gray-200) for grid; dark mode uses `#d1d5db` (gray-300) and `#374151` (gray-700).

  **Must NOT do**:
  - Do NOT register controllers/elements individually — `registerables` is fine.
  - Do NOT call `Chart.register` at module top level (would fire during SSR import).
  - Do NOT inject a `<ThemeProvider>` or context — pass `isDark` as a prop to chart components.

  **Recommended Agent Profile**:
  - **Category**: `quick` — single helper module.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T17, T18
  - **Blocked By**: T1

  **References**:
  - Chart.js v4 registration docs: `https://www.chartjs.org/docs/latest/getting-started/integration.html#bundle-optimization` — confirms `registerables` is the idiomatic catch-all.
  - `svelte-chartjs` README — confirms chart components need Chart.js registered before they instantiate.

  **Acceptance Criteria**:
  - [ ] `ensureChartJsRegistered` exists and is idempotent
  - [ ] No top-level `Chart.register` call (only inside the function)
  - [ ] `chartThemeColors(false)` returns `{ tick: '#374151', grid: '#e5e7eb', legend: '#374151' }`
  - [ ] `chartThemeColors(true)` returns dark variants

  **QA Scenarios**:
  ```
  Scenario: Idempotent registration
    Tool: Bash
    Steps:
      1. Evidence script imports ensureChartJsRegistered, calls it twice, ensures no error and Chart.registry has bar+doughnut controllers registered.
      2. Save Chart.registry.getController('bar') !== undefined check to .omo/evidence/task-7-registration.txt
    Expected Result: 'bar' controller present; second call doesn't throw
    Evidence: .omo/evidence/task-7-registration.txt

  Scenario: SSR-safety check (top-level register would crash)
    Tool: Bash
    Steps:
      1. grep -n "Chart\.register" src/lib/chart/chartSetup.ts > .omo/evidence/task-7-ssr-safety.txt
      2. Assert only one match, and it's inside a function body (not column 0).
    Expected Result: single match, indented (inside function)
    Failure Indicators: multiple matches; column-0 match (would mean top-level call)
    Evidence: .omo/evidence/task-7-ssr-safety.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-7-registration.txt`
  - [ ] `task-7-ssr-safety.txt`

  **Commit**: YES — `feat(chart): idempotent chart.js registration + theme color helpers`. Files: `src/lib/chart/chartSetup.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 8. **Tailwind dark-mode config + FOUT-prevention script + global CSS** — `tailwind.config.{js,ts}`, `src/app.html`, `src/app.css`

  **What to do**:
  - **`tailwind.config.{js,ts}`** — ensure `darkMode: 'class'` (T1 set this; confirm it's intact).
  - **`src/app.html`** — insert an inline `<script>` BEFORE the `%sveltekit.head%` placeholder, inside `<head>`. This script runs synchronously, before paint, preventing FOUT:
    ```html
    <script>
      (function () {
        try {
          var t = localStorage.getItem('theme');
          if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
          }
        } catch (_) {}
      })();
    </script>
    ```
  - **`src/app.css`** (or `src/routes/+layout.svelte` `<style global>` — pick the SvelteKit convention; `app.css` imported in layout is cleanest):
    ```css
    @tailwind base;
    @tailwind components;
    @tailwind utilities;

    @layer base {
      body { @apply bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100 transition-colors; }
    }
    ```
    The `body` rule is the **only** allowed use of `@apply` (per guardrails).
  - Ensure `src/app.css` is imported from `src/routes/+layout.svelte` (`import '../app.css';`).

  **Must NOT do**:
  - Do NOT use `darkMode: 'media'`.
  - Do NOT put the theme-init script inside a Svelte component — it must be in static `app.html` so it runs before hydration.
  - Do NOT add additional `@apply` rules beyond the body.
  - Do NOT use a `<svelte:head>` element to set the dark class — it runs too late, causing FOUT.

  **Recommended Agent Profile**:
  - **Category**: `quick` — config + 2 small files.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T13
  - **Blocked By**: T1

  **References**:
  - Tailwind dark mode: `https://tailwindcss.com/docs/dark-mode#toggling-dark-mode-manually` — confirms the `localStorage` + class-on-`<html>` pattern.
  - SvelteKit `app.html`: `https://svelte.dev/docs/kit/project-structure#Project-files-src-app-html` — explains it's a static template, not a Svelte component.

  **Acceptance Criteria**:
  - [ ] `tailwind.config.*` contains `darkMode: 'class'`
  - [ ] `src/app.html` contains the inline init script *inside* `<head>` and *before* `%sveltekit.head%`
  - [ ] `src/app.css` exists with `@tailwind` directives and the single `@apply` body rule
  - [ ] `src/routes/+layout.svelte` imports `../app.css`
  - [ ] `npm run dev` then visiting `/` with `localStorage.theme = 'dark'` (set via DevTools or a Playwright `addInitScript`) produces a dark background on first paint (no flash)

  **QA Scenarios**:
  ```
  Scenario: FOUT-free dark mode initialization (Playwright)
    Tool: Playwright (via playwright skill)
    Preconditions: dev server running
    Steps:
      1. await page.addInitScript(() => localStorage.setItem('theme', 'dark'));
      2. await page.goto('http://localhost:5173/');
      3. await page.screenshot({ path: '.omo/evidence/task-8-dark-first-paint.png' });
      4. const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      5. const hasDarkClass = await page.evaluate(() => document.documentElement.classList.contains('dark'));
      6. write { bg, hasDarkClass } to .omo/evidence/task-8-dark-state.json
    Expected Result: hasDarkClass === true; bg is a dark color (rgb r+g+b sum < 200)
    Failure Indicators: hasDarkClass === false; bg is white
    Evidence: .omo/evidence/task-8-dark-first-paint.png, .omo/evidence/task-8-dark-state.json

  Scenario: @apply guardrail (only on body)
    Tool: Bash
    Steps:
      1. grep -nE "@apply" src/app.css src/**/*.svelte 2>/dev/null | tee .omo/evidence/task-8-apply-grep.txt
      2. Assert exactly one match, in src/app.css, on a line containing 'body'.
    Expected Result: exactly one match, on body line
    Failure Indicators: multiple matches; match outside body line
    Evidence: .omo/evidence/task-8-apply-grep.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-8-dark-first-paint.png`
  - [ ] `task-8-dark-state.json`
  - [ ] `task-8-apply-grep.txt`

  **Commit**: YES — `feat(theme): tailwind dark-mode + FOUT-free init script`. Files: `tailwind.config.*`, `src/app.html`, `src/app.css`, `src/routes/+layout.svelte`. Pre-commit: `npx tsc --noEmit && npm run build`.

- [x] 9. **Default category seed data** — `src/lib/repos/seed.ts`

  **What to do**:
  - Create `src/lib/repos/seed.ts` exporting:
    ```ts
    import type { Category, Expense } from '$types';
    import { UNCATEGORIZED_ID } from '$types';
    import { colorForCategoryId, UNCATEGORIZED_COLOR } from '$utils/categoryColor';

    export function defaultCategories(): Category[] {
      const defaults = [
        { id: UNCATEGORIZED_ID, name: 'Uncategorized', color: UNCATEGORIZED_COLOR },
        { id: 'cat-food', name: 'Food', color: colorForCategoryId('cat-food') },
        { id: 'cat-transport', name: 'Transport', color: colorForCategoryId('cat-transport') },
        { id: 'cat-bills', name: 'Bills', color: colorForCategoryId('cat-bills') },
        { id: 'cat-entertainment', name: 'Entertainment', color: colorForCategoryId('cat-entertainment') },
        { id: 'cat-shopping', name: 'Shopping', color: colorForCategoryId('cat-shopping') },
      ];
      return defaults;
    }
    export function sampleExpenses(): Expense[] { /* ~15 expenses spread across the trailing 12 months across multiple categories, used to make the dashboard non-empty on first load */ }
    ```
  - Sample expenses must:
    - Span at least 6 different months across the trailing 12
    - Use a mix of category IDs (not all the same category)
    - Have realistic amounts (`12.50`, `89.99`, `4.20`, etc. — not all integers)
    - Have varied notes (`"Lunch"`, `"Bus pass"`, `"Electricity"`, `""`)
    - Use ids `'exp-001'` through `'exp-015'` for determinism in tests
    - Use today-relative dates computed at *runtime* using a helper, so the seed always renders in the current trailing-12-month window (do NOT hardcode `'2024-...'` dates which will fall off the chart as time passes)

  **Must NOT do**:
  - Do NOT include any `Uncategorized`-bound seed expenses (so the cascade test in T12 has a clean before-state).
  - Do NOT include speculative fields.
  - Do NOT make the seed function async.
  - Do NOT depend on the future store module — pure data.

  **Recommended Agent Profile**:
  - **Category**: `quick` — data file with two factory functions.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Blocks**: T10
  - **Blocked By**: T1, T2

  **References**:
  - T2 (Expense/Category types), T4 (color hash for default categories).
  - Metis directive: defaults exist, Uncategorized is always present, cascade target.

  **Acceptance Criteria**:
  - [ ] `defaultCategories()` returns 6 entries; first is Uncategorized with `UNCATEGORIZED_COLOR`
  - [ ] `defaultCategories()` is referentially stable on repeated calls (deep-equal to itself)
  - [ ] `sampleExpenses()` returns ≥ 12 entries
  - [ ] Sample expense dates all fall within `last12MonthKeys()` window (test using T5's utility)
  - [ ] No sample expense uses `UNCATEGORIZED_ID`
  - [ ] No two sample expenses share an `id`

  **QA Scenarios**:
  ```
  Scenario: Seed shape + window invariant
    Tool: Bash
    Steps:
      1. Evidence script imports defaultCategories + sampleExpenses + last12MonthKeys
      2. Assert: 6 cats, Uncategorized first, 15 expenses, all monthKey(date) ∈ last12MonthKeys
      3. Print summary { catCount, expCount, monthsCovered, uncategorizedInSample } to .omo/evidence/task-9-seed.json
    Expected Result: all assertions pass; uncategorizedInSample === false
    Failure Indicators: any failure
    Evidence: .omo/evidence/task-9-seed.json

  Scenario: No hardcoded year-strings (future-proofing check)
    Tool: Bash
    Steps:
      1. grep -nE "['\"]20[0-9]{2}-" src/lib/repos/seed.ts > .omo/evidence/task-9-no-hardcoded-dates.txt || true
      2. test ! -s .omo/evidence/task-9-no-hardcoded-dates.txt && echo "OK" >> .omo/evidence/task-9-no-hardcoded-dates.txt
    Expected Result: "OK" (dates are computed, not literal)
    Evidence: .omo/evidence/task-9-no-hardcoded-dates.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-9-seed.json`
  - [ ] `task-9-no-hardcoded-dates.txt`

  **Commit**: YES — `feat(repos): default category + sample expense seed`. Files: `src/lib/repos/seed.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 10. **Mock data store (in-memory + localStorage persistence)** — `src/lib/repos/mockStore.ts`

  **What to do**:
  - Create `src/lib/repos/mockStore.ts` — a single module that owns the in-memory state and persists it to `localStorage`. Both Mock repositories read/write through this store so cascade updates remain atomic.
  - Exports:
    ```ts
    import type { Expense, Category } from '$types';
    export interface MockStoreState { categories: Category[]; expenses: Expense[]; }
    export function getStore(): MockStoreState;             // returns deep copy
    export function setStore(updater: (s: MockStoreState) => void): MockStoreState; // mutates inside, persists, returns new deep copy
    export function resetStore(): void;                     // wipes localStorage + reseeds (for tests)
    export const LS_KEY = 'expense-tracker:store:v1';
    ```
  - On first access, if `localStorage[LS_KEY]` is missing or malformed, populate from `defaultCategories()` + `sampleExpenses()` (T9) and persist.
  - Guard all `localStorage` access in `try/catch` and treat any failure as "use in-memory only this session".
  - SSR safety: at module top level, do NOT touch `localStorage`. Initialize lazily inside `getStore`/`setStore`, behind a `typeof localStorage === 'undefined'` check that returns the seeded in-memory state. The module must be safe to import in SSR (the layout will import it via the stores in T14).
  - `setStore` accepts an *updater function* (not a value) to make cascade operations transactional — the updater sees one consistent state, mutates the draft, and the store re-serializes.

  **Must NOT do**:
  - Do NOT export the raw mutable state object (always deep-copy on read).
  - Do NOT simulate async/latency.
  - Do NOT add retries, error recovery beyond the `try/catch` on localStorage.
  - Do NOT use `JSON.parse(JSON.stringify(...))` more than once per access (it's fine to use; just don't litter it).
  - Do NOT use `structuredClone` if SSR target is older (Node 16+) — be defensive.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — non-trivial: SSR safety + persistence + deep-copy semantics + transactional updater.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (within Wave 3 — T11/T12 depend on this)
  - **Parallel Group**: Wave 3 sub-step 1
  - **Blocks**: T11, T12
  - **Blocked By**: T1, T2, T9

  **References**:
  - T2 (types), T9 (seed data).
  - Metis directive: "single store module so cascade is atomic; SSR-safe; deep-copy semantics."

  **Acceptance Criteria**:
  - [ ] Module compiles and is importable from server-rendered context (no top-level `localStorage` reference)
  - [ ] On first browser load with empty `localStorage`, `getStore()` returns the seed
  - [ ] `setStore(s => s.expenses.push({...}))` persists the change to `localStorage` and a fresh `getStore()` reflects it
  - [ ] `getStore()` returns a deep copy — mutating the returned object does NOT affect subsequent `getStore()` calls
  - [ ] `resetStore()` wipes `localStorage[LS_KEY]` and re-seeds

  **QA Scenarios**:
  ```
  Scenario: Persistence + deep-copy semantics (browser)
    Tool: Playwright
    Steps:
      1. page.goto('about:blank'); attach evidence script that imports mockStore via ES module
      2. Reset, then call setStore to add a custom category 'Test'
      3. Reload page; getStore should still contain 'Test'
      4. Mutate returned categories array; getStore again; mutation should not have leaked
      5. Save state to .omo/evidence/task-10-persistence.json
    Expected Result: 'Test' persists across reload; mutation isolation holds
    Failure Indicators: 'Test' missing after reload; mutation leaks
    Evidence: .omo/evidence/task-10-persistence.json

  Scenario: SSR-safety (no localStorage at import time)
    Tool: Bash
    Steps:
      1. node --input-type=module -e "import('./src/lib/repos/mockStore.ts').then(m => console.log(Object.keys(m)))" 2>&1 | tee .omo/evidence/task-10-ssr-import.txt
      2. (Use tsx or ts-node if .ts can't be loaded directly)
    Expected Result: prints keys (getStore, setStore, resetStore, LS_KEY) without "localStorage is not defined" error
    Failure Indicators: ReferenceError
    Evidence: .omo/evidence/task-10-ssr-import.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-10-persistence.json`
  - [ ] `task-10-ssr-import.txt`

  **Commit**: YES — `feat(repos): mock data store with localStorage + ssr-safe`. Files: `src/lib/repos/mockStore.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 11. **MockExpenseRepository** — `src/lib/repos/mockExpenseRepository.ts`

  **What to do**:
  - Implement `ExpenseRepository` against `mockStore`:
    ```ts
    export class MockExpenseRepository implements ExpenseRepository {
      async list(query?: ListExpensesQuery): Promise<Expense[]> {
        const s = getStore();
        const sorted = [...s.expenses].sort((a, b) => b.date.localeCompare(a.date));
        const offset = query?.offset ?? 0;
        const limit = query?.limit ?? sorted.length;
        return sorted.slice(offset, offset + limit);
      }
      async create(input) { /* generate id (crypto.randomUUID), setStore(s => s.expenses.push(...)), return new */ }
      async update(id, patch) { /* find; throw NOT_FOUND if missing; setStore(s => Object.assign(s.expenses[i], patch)); return updated */ }
      async delete(id) { /* setStore(s => s.expenses = s.expenses.filter(e => e.id !== id)) */ }
    }
    export const expenseRepository: ExpenseRepository = new MockExpenseRepository();
    ```
  - Export a singleton `expenseRepository` so the Svelte stores in T14 import the same instance.
  - The newest-first sort happens at the repo boundary (NOT in the UI). The user-decided invariant "sort by date, newest first" lives here.
  - All methods return deep copies via the store's contract.

  **Must NOT do**:
  - Do NOT add `findById`, `findByCategory`, `getStats`, etc.
  - Do NOT simulate latency or random failures.
  - Do NOT skip the `throw NOT_FOUND` branch on update of a missing id — the future API will return 404.
  - Do NOT call the categories side of the store from this file.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — straightforward but must respect contracts (deep copy, NOT_FOUND, sort invariant).
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES with T12 (Wave 3 sub-step 2)
  - **Blocks**: T14
  - **Blocked By**: T1, T3, T10

  **References**:
  - T3 (interfaces), T10 (store contract).

  **Acceptance Criteria**:
  - [ ] All 4 interface methods implemented; class compiles
  - [ ] `list()` returns expenses sorted by `date` descending
  - [ ] `list({ limit: 5 })` returns at most 5 entries
  - [ ] `list({ offset: 5 })` skips first 5
  - [ ] `create()` returns the new entry with a generated id; subsequent `list()` includes it
  - [ ] `update(unknownId, ...)` throws `RepositoryError` with code `'NOT_FOUND'`
  - [ ] `delete(id)` removes only that expense; others remain

  **QA Scenarios**:
  ```
  Scenario: CRUD round-trip + sort + pagination
    Tool: Playwright (browser env so localStorage works) OR Bash with happy-dom
    Steps:
      1. Reset store (T10 resetStore). Get list — assert sorted desc by date.
      2. Create 3 expenses with dates 2026-01-01, 2026-03-01, 2026-02-01.
      3. List — assert order [2026-03-01, 2026-02-01, 2026-01-01, ...seeded...].
      4. Update one — verify patch applied.
      5. Delete one — verify removed.
      6. Try update(unknown-id) → expect throw with code NOT_FOUND.
      7. Save observations to .omo/evidence/task-11-crud.json
    Expected Result: every assertion passes
    Evidence: .omo/evidence/task-11-crud.json

  Scenario: No speculative methods (negative)
    Tool: Bash
    Steps:
      1. grep -nE "(findBy|getStats|bulkCreate)" src/lib/repos/mockExpenseRepository.ts > .omo/evidence/task-11-no-spec.txt || true
      2. test ! -s .omo/evidence/task-11-no-spec.txt && echo "OK" >> .omo/evidence/task-11-no-spec.txt
    Expected Result: "OK"
    Evidence: .omo/evidence/task-11-no-spec.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-11-crud.json`
  - [ ] `task-11-no-spec.txt`

  **Commit**: YES — `feat(repos): mock expense repository`. Files: `src/lib/repos/mockExpenseRepository.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 12. **MockCategoryRepository (with cascade-to-Uncategorized)** — `src/lib/repos/mockCategoryRepository.ts`

  **What to do**:
  - Implement `CategoryRepository`:
    ```ts
    export class MockCategoryRepository implements CategoryRepository {
      async list() { return getStore().categories; }
      async create(input) { /* generate id, setStore(s => s.categories.push(...)), return new */ }
      async update(id, patch) {
        if (id === UNCATEGORIZED_ID && patch.name) {
          throw new RepositoryError('IMMUTABLE', 'Uncategorized cannot be renamed');
        }
        // ...patch by id; throw NOT_FOUND if missing
      }
      async delete(id) {
        if (id === UNCATEGORIZED_ID) throw new RepositoryError('IMMUTABLE', 'Uncategorized cannot be deleted');
        // Cascade reassign: in a single setStore call, both remove the category AND reassign expenses
        setStore(s => {
          s.categories = s.categories.filter(c => c.id !== id);
          for (const e of s.expenses) if (e.categoryId === id) e.categoryId = UNCATEGORIZED_ID;
        });
      }
    }
    export const categoryRepository: CategoryRepository = new MockCategoryRepository();
    ```
  - The delete cascade MUST happen inside a single `setStore` updater call so the state is consistent — observers should never see a state where a category is gone but expenses still reference it.
  - Name uniqueness is enforced at the repo layer: `create` and `update` throw `RepositoryError('VALIDATION', ...)` if another category (different id) has the same name. Case-insensitive comparison after trim.

  **Must NOT do**:
  - Do NOT allow delete or rename of `Uncategorized`.
  - Do NOT split the cascade into two `setStore` calls.
  - Do NOT silently allow duplicate category names.
  - Do NOT add `findBy*` methods.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — cascade + uniqueness + immutability all in one file. Care required.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES with T11 (Wave 3 sub-step 2)
  - **Blocks**: T14
  - **Blocked By**: T1, T3, T10

  **References**:
  - T3 (interfaces), T10 (store), T2 (UNCATEGORIZED_ID).
  - Metis directive: cascade-to-Uncategorized; Uncategorized non-deletable; uniqueness.

  **Acceptance Criteria**:
  - [ ] All 4 methods implemented
  - [ ] `delete(UNCATEGORIZED_ID)` throws `IMMUTABLE`
  - [ ] `update(UNCATEGORIZED_ID, { name: 'X' })` throws `IMMUTABLE`; updating its color is allowed (since color override is a user pref)
  - [ ] `create({ name: 'Food', color: '#...' })` throws `VALIDATION` when 'Food' already exists
  - [ ] `delete(catId)` reassigns all expenses with that `categoryId` to `UNCATEGORIZED_ID` *in the same `setStore` call*
  - [ ] After cascade, the affected expenses are still present (only their categoryId changed)

  **QA Scenarios**:
  ```
  Scenario: Cascade-to-Uncategorized atomicity
    Tool: Playwright
    Steps:
      1. Reset store. Create category 'TempCat' with id ct1.
      2. Create 2 expenses with categoryId = 'ct1'.
      3. Call categoryRepository.delete('ct1').
      4. Read store: assert 'ct1' is gone from categories; assert those 2 expenses still exist with categoryId === UNCATEGORIZED_ID.
      5. Save observed state to .omo/evidence/task-12-cascade.json
    Expected Result: category removed, expenses present with uncategorized id
    Failure Indicators: expenses deleted; expenses still reference 'ct1'; orphan category
    Evidence: .omo/evidence/task-12-cascade.json

  Scenario: Immutability of Uncategorized
    Tool: Bash (browser context via happy-dom or playwright)
    Steps:
      1. Try categoryRepository.delete(UNCATEGORIZED_ID) — capture throw.code
      2. Try categoryRepository.update(UNCATEGORIZED_ID, { name: 'Other' }) — capture throw.code
      3. Try categoryRepository.update(UNCATEGORIZED_ID, { color: '#000000' }) — should SUCCEED
      4. Save all 3 outcomes to .omo/evidence/task-12-immutable.json
    Expected Result: first two throw 'IMMUTABLE'; third succeeds
    Evidence: .omo/evidence/task-12-immutable.json

  Scenario: Name uniqueness (negative)
    Tool: same as above
    Steps:
      1. Reset. Try create with name 'Food' (already seeded).
      2. Capture throw.code; expect 'VALIDATION'.
      3. Try create with name '  food  ' (whitespace + case) → also 'VALIDATION'.
    Expected Result: both throw VALIDATION
    Evidence: .omo/evidence/task-12-uniqueness.json
  ```

  **Evidence to Capture**:
  - [ ] `task-12-cascade.json`
  - [ ] `task-12-immutable.json`
  - [ ] `task-12-uniqueness.json`

  **Commit**: YES — `feat(repos): mock category repository with cascade + immutability`. Files: `src/lib/repos/mockCategoryRepository.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 13. **Root +layout.svelte (top nav + theme toggle + dark-mode JS hookup)** — `src/routes/+layout.svelte`

  **What to do**:
  - `src/routes/+layout.svelte` (Svelte 5 runes or Svelte 4 syntax, whichever the scaffold produced):
    - Import `'../app.css'`.
    - Render a sticky top nav with: app title `Expenses`, two nav links — `/` ("Dashboard") and `/categories` ("Categories"), and a theme-toggle button on the right.
    - The active link gets an underline / different color (use `$page.url.pathname` to detect).
    - Theme toggle button has `data-testid="theme-toggle"`. On click: read `document.documentElement.classList.contains('dark')`, flip it, write the new value (`'light'` or `'dark'`) to `localStorage.theme`.
    - The page content slot is below the nav; constrain it with a `<main class="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">` wrapper.
    - Mobile responsive: on `< 640px` (Tailwind's default), nav links can stack or use abbreviated labels — keep it simple, no hamburger menu needed (two items).
    - Use Unicode glyphs for the toggle icon (`☀` light, `🌙` dark) — no icon library.

  **Must NOT do**:
  - Do NOT create a `<ThemeProvider>` component or theme store.
  - Do NOT set the dark class via `onMount` (the inline script in `app.html` already did it — `onMount` runs too late and causes flicker).
  - Do NOT add a hamburger menu.
  - Do NOT use `<svelte:head>` to set the dark class.
  - Do NOT add settings, profile, or user-account UI elements.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — layout + interactive theme toggle.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 4)
  - **Blocks**: T19, T20
  - **Blocked By**: T1, T8

  **References**:
  - T8 (Tailwind dark config + FOUT script).
  - SvelteKit layouts: `https://svelte.dev/docs/kit/routing#layout`.
  - `$page.url.pathname` from `$app/stores`.

  **Acceptance Criteria**:
  - [ ] `+layout.svelte` exists with nav, both links, theme toggle
  - [ ] Active route link has a distinctive style
  - [ ] Theme toggle persists choice and applies/removes `dark` class on `<html>`
  - [ ] Both routes show the same nav (slot pattern works)

  **QA Scenarios**:
  ```
  Scenario: Theme toggle round-trip + persistence (Playwright)
    Tool: Playwright
    Steps:
      1. page.goto('http://localhost:5173/');
      2. Capture initial classList.dark state → S0.
      3. page.click('[data-testid="theme-toggle"]');
      4. Capture classList.dark → S1 (should be !S0).
      5. Capture localStorage.theme value.
      6. page.reload();
      7. Capture classList.dark → S2 (should equal S1).
      8. Screenshot before and after toggle: .omo/evidence/task-13-toggle-before.png and -after.png
      9. Save state log to .omo/evidence/task-13-toggle-state.json
    Expected Result: S1 = !S0; S2 = S1; localStorage holds the toggled value
    Failure Indicators: toggle no-op; state doesn't persist
    Evidence: .omo/evidence/task-13-toggle-*.{png,json}

  Scenario: Nav active-link styling
    Tool: Playwright
    Steps:
      1. Visit '/'; capture computed style of dashboard link vs. categories link → assert different.
      2. Visit '/categories'; capture again → assert roles swapped.
      3. Save to .omo/evidence/task-13-nav-active.json
    Expected Result: active link visually distinct on each route
    Evidence: .omo/evidence/task-13-nav-active.json
  ```

  **Evidence to Capture**:
  - [ ] `task-13-toggle-before.png`, `task-13-toggle-after.png`, `task-13-toggle-state.json`
  - [ ] `task-13-nav-active.json`

  **Commit**: YES — `feat(layout): root layout, nav, and theme toggle`. Files: `src/routes/+layout.svelte`. Pre-commit: `npx tsc --noEmit && npm run build`.

- [x] 14. **Svelte writable stores (expenses, categories)** — `src/lib/stores/expenses.ts`, `src/lib/stores/categories.ts`

  **What to do**:
  - `src/lib/stores/expenses.ts`:
    ```ts
    import { writable } from 'svelte/store';
    import type { Expense } from '$types';
    import { expenseRepository } from '$repos/mockExpenseRepository';
    export const expenses = writable<Expense[]>([]);
    export async function refreshExpenses() { expenses.set(await expenseRepository.list()); }
    export async function addExpense(input) { await expenseRepository.create(input); await refreshExpenses(); }
    export async function editExpense(id, patch) { await expenseRepository.update(id, patch); await refreshExpenses(); }
    export async function deleteExpense(id) { await expenseRepository.delete(id); await refreshExpenses(); }
    ```
  - `src/lib/stores/categories.ts`: analogous, with `addCategory`, `editCategory`, `deleteCategoryWithCascade` (the cascade is implicit in the repo's delete, but the wrapper also calls `refreshExpenses` after, since cascade affects expenses).
  - The wrapper `deleteCategoryWithCascade` MUST call both `refreshCategories()` AND `refreshExpenses()` after the repo delete returns — otherwise the UI shows stale `categoryId` references.
  - Both files are SSR-safe: only `writable(...)` runs at import time. The async functions run in event handlers (browser only).
  - No `derived` stores in this task — add them later only if a derived value is used in 3+ places.

  **Must NOT do**:
  - Do NOT call `refreshExpenses()` at module top level — components call it in `onMount`.
  - Do NOT use Svelte 5 `$state` runes if the scaffold is Svelte 4; use plain `writable`. (If Svelte 5, prefer runes inside .svelte files but stores remain plain.)
  - Do NOT add a `loading` boolean — mock is synchronous-ish; user explicitly forbade simulated latency.
  - Do NOT add derived stores in this task.
  - Do NOT call `expenseRepository` directly from .svelte components — go through these wrappers.

  **Recommended Agent Profile**:
  - **Category**: `quick` — thin wrapper module.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 4)
  - **Blocks**: T15, T16, T17, T18, T20
  - **Blocked By**: T1, T11, T12

  **References**:
  - Svelte stores: `https://svelte.dev/docs/svelte/stores`.
  - T11, T12 (repo singletons).

  **Acceptance Criteria**:
  - [ ] Both store files exist with `writable` + `refresh*` + CRUD wrappers
  - [ ] `deleteCategoryWithCascade` calls both `refreshCategories()` and `refreshExpenses()` after the repo call
  - [ ] No top-level repo calls (verified by `grep -n "refresh" src/lib/stores/*.ts | head` — should not show line 1 of either file)
  - [ ] `npx tsc --noEmit` passes

  **QA Scenarios**:
  ```
  Scenario: Cascade refresh both stores
    Tool: Playwright
    Steps:
      1. page.goto root, wait for initial expenses to render
      2. From the page console: import stores + call addCategory; addExpense bound to that category
      3. Subscribe to both stores; capture values
      4. Call deleteCategoryWithCascade for that category
      5. Capture both store values after the call
      6. Assert: categories no longer contains it; expenses now show categoryId = UNCATEGORIZED_ID for that one
      7. Save observations to .omo/evidence/task-14-cascade-refresh.json
    Expected Result: both stores reflect the cascade after a single deleteCategoryWithCascade call
    Failure Indicators: stale data in either store
    Evidence: .omo/evidence/task-14-cascade-refresh.json

  Scenario: No top-level side effects (SSR safety)
    Tool: Bash
    Steps:
      1. Static scan: head -20 of each store file; assert no `refresh*()` call at column 0
      2. Save to .omo/evidence/task-14-ssr-static.txt
    Expected Result: no top-level invocations
    Evidence: .omo/evidence/task-14-ssr-static.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-14-cascade-refresh.json`
  - [ ] `task-14-ssr-static.txt`

  **Commit**: YES — `feat(stores): writable stores + crud wrappers for expenses/categories`. Files: `src/lib/stores/expenses.ts`, `src/lib/stores/categories.ts`. Pre-commit: `npx tsc --noEmit`.

- [x] 15. **Expense list component (rows + empty state + inline delete-confirm)** — `src/lib/components/ExpenseList.svelte`

  **What to do**:
  - `src/lib/components/ExpenseList.svelte`:
    - Renders `$expenses` from the store as a vertically stacked list (table-like on desktop, card-like on mobile via Tailwind responsive classes).
    - Each row shows: a small color dot (using `category.color`), the category name, the formatted amount (right-aligned, using `formatAmount`), the date (formatted `MMM D, YYYY`), the note (truncated with `truncate`), and on the right: ✎ edit button + 🗑 delete button.
    - Looks up category color/name via the `$categories` store. Use a `Map<id, Category>` recomputed reactively (since categories list is short).
    - Empty state: when `$expenses.length === 0`, render a centered block with `data-testid="empty-state"`, text `"No expenses yet."` and a brief hint `"Click + Add expense to get started."` (the button itself lives on the parent dashboard, not in this component).
    - Edit button click: dispatches a custom event `edit` with the expense as detail. Parent (dashboard) opens the modal.
    - Delete button click: switches that row into an inline "confirm" state — the row temporarily replaces ✎/🗑 with `Delete` (red) and `Cancel` (gray) buttons. Clicking Delete calls `deleteExpense(id)` then exits confirm state. Clicking Cancel exits confirm state. Confirming a different row exits the previous one's confirm state.
    - Every row carries `data-testid="expense-row"`, `data-expense-id={expense.id}`. Buttons have `data-testid="expense-edit-btn"`, `data-testid="expense-delete-btn"`, `data-testid="expense-delete-confirm-btn"`, `data-testid="expense-delete-cancel-btn"`.
    - Use Unicode `✎` and `🗑` (NOT an icon library).
    - On mount: call `refreshExpenses()` and `refreshCategories()` (idempotent — first dashboard mount triggers initial load).

  **Must NOT do**:
  - Do NOT create a separate `<ExpenseRow>` component — keep rows inline in this file (they aren't reused elsewhere; over-componentization is what Metis warned against).
  - Do NOT add filter, sort, search, or pagination controls.
  - Do NOT call `alert()` for delete confirmation — must be inline.
  - Do NOT use a date library to format the date — `Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(date))`.
  - Do NOT use `<Modal>` for the delete confirm — strictly inline.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — UI component with interaction state.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 4)
  - **Blocks**: T19
  - **Blocked By**: T1, T2, T4, T6, T14

  **References**:
  - T4 (color), T6 (formatter), T14 (store).
  - Tailwind responsive prefixes: `https://tailwindcss.com/docs/responsive-design`.

  **Acceptance Criteria**:
  - [ ] Component renders the seeded sample expenses on first mount
  - [ ] Rows display: color dot, category name, formatted amount (2dp), date (e.g., "May 15, 2026"), note
  - [ ] Click ✎ on a row dispatches `edit` event with the expense
  - [ ] Click 🗑 enters inline confirm state for that row; Delete removes it; Cancel reverts
  - [ ] Confirming on a second row exits the first row's confirm state
  - [ ] Empty state renders when list is empty
  - [ ] Mobile viewport: rows stack readably; no horizontal scrollbar

  **QA Scenarios**:
  ```
  Scenario: Delete with inline confirm (happy path)
    Tool: Playwright
    Preconditions: page with ExpenseList mounted (used in dashboard at this point — see T19; for isolated QA, use a temporary `/dev/expense-list` route OR test via the dashboard)
    Steps:
      1. await page.goto('http://localhost:5173/');
      2. const beforeCount = await page.locator('[data-testid="expense-row"]').count();
      3. await page.locator('[data-testid="expense-row"]').first().locator('[data-testid="expense-delete-btn"]').click();
      4. await expect(page.locator('[data-testid="expense-delete-confirm-btn"]')).toBeVisible();
      5. await page.locator('[data-testid="expense-delete-confirm-btn"]').click();
      6. await expect(page.locator('[data-testid="expense-row"]')).toHaveCount(beforeCount - 1);
      7. await page.screenshot({ path: '.omo/evidence/task-15-delete-after.png' });
    Expected Result: count decremented by exactly 1
    Failure Indicators: count unchanged; multiple deletions; confirm button not visible
    Evidence: .omo/evidence/task-15-delete-after.png, .omo/evidence/task-15-delete-counts.json

  Scenario: Cancel delete confirm (negative path)
    Tool: Playwright
    Steps:
      1. await page.goto('http://localhost:5173/');
      2. count rows → C0
      3. click first row's 🗑 → confirm button visible
      4. click cancel button → confirm button gone
      5. count rows → C1; assert C1 === C0
      6. Save to .omo/evidence/task-15-cancel.json
    Expected Result: no change in row count; confirm UI dismissed
    Evidence: .omo/evidence/task-15-cancel.json

  Scenario: Empty state
    Tool: Playwright
    Steps:
      1. In an init script: localStorage.setItem('expense-tracker:store:v1', JSON.stringify({ categories: [/* defaults */], expenses: [] }));
      2. goto / → expect [data-testid="empty-state"] visible; expense-row count === 0
      3. Screenshot: .omo/evidence/task-15-empty-state.png
    Expected Result: empty state visible
    Evidence: .omo/evidence/task-15-empty-state.png

  Scenario: Mobile layout (375px viewport)
    Tool: Playwright
    Steps:
      1. await page.setViewportSize({ width: 375, height: 667 });
      2. goto /; capture document.body.scrollWidth === window.innerWidth (no horizontal overflow)
      3. Screenshot: .omo/evidence/task-15-mobile.png
    Expected Result: no horizontal scroll; rows readable
    Evidence: .omo/evidence/task-15-mobile.png
  ```

  **Evidence to Capture**:
  - [ ] `task-15-delete-after.png`, `task-15-delete-counts.json`
  - [ ] `task-15-cancel.json`
  - [ ] `task-15-empty-state.png`
  - [ ] `task-15-mobile.png`

  **Commit**: YES — `feat(components): expense list with inline delete-confirm + empty state`. Files: `src/lib/components/ExpenseList.svelte`. Pre-commit: `npx tsc --noEmit && npx svelte-check`.

- [x] 16. **Expense Add/Edit modal (single shared component)** — `src/lib/components/ExpenseFormModal.svelte`

  **What to do**:
  - `src/lib/components/ExpenseFormModal.svelte`:
    - Props:
      - `open: boolean` — whether the modal is rendered
      - `expense?: Expense` — when present, the form is in Edit mode (pre-filled, submits via `editExpense`); when absent, Add mode (submits via `addExpense`)
    - Dispatches: `close` event when user dismisses (Esc, backdrop click, Cancel button, or successful submit).
    - Renders an accessible modal:
      - Backdrop: full-screen semi-transparent overlay with `data-testid="modal-backdrop"`. Clicking it dispatches `close`.
      - Dialog box: centered card with title `Add expense` or `Edit expense`. On mobile (`< 640px`), the dialog occupies the full screen.
      - Form fields (all with `data-testid` and labels):
        - `amount` — `<input type="number" step="0.01" min="0">` (`data-testid="amount-input"`)
        - `date` — `<input type="date">`, defaults to `todayIso()` in Add mode (`data-testid="date-input"`)
        - `categoryId` — `<select>` populated from `$categories` (`data-testid="category-select"`)
        - `note` — `<input type="text" maxlength="200">` (`data-testid="note-input"`)
      - Submit button (`data-testid="modal-submit"`) and Cancel button (`data-testid="modal-cancel"`).
      - Inline error messages under fields with `data-testid="amount-error"`, `data-testid="date-error"`, `data-testid="category-error"`.
    - Validation (single `validate()` function — no library):
      - amount: required, must parse via `parseAmountInput` (non-null, positive)
      - date: required, must match `/^\d{4}-\d{2}-\d{2}$/` and be a valid date string
      - categoryId: required, must exist in `$categories`
      - note: optional, ≤ 200 chars
    - On submit: if validation fails, render inline errors and DO NOT call the store. If valid, call `addExpense`/`editExpense`, then dispatch `close`.
    - Escape key: dispatches `close`. Use `<svelte:window on:keydown>` while open. Focus trap: focus the amount input on mount; restore prior focus on close (a small `tabindex` trap is acceptable — full WAI-ARIA isn't required at this scope, but Esc + backdrop click are mandatory).
    - When opened in Edit mode, all four fields are pre-filled from the `expense` prop. Submission patches only changed fields (or the entire object — simpler is fine).

  **Must NOT do**:
  - Do NOT use `<dialog>` element if it complicates SSR — a styled `<div>` with `role="dialog"` is acceptable.
  - Do NOT pull in `zod`, `superforms`, `formik`-equivalent, etc.
  - Do NOT create separate Add and Edit modals.
  - Do NOT create a `<Button>` wrapper for the submit/cancel buttons.
  - Do NOT use `alert()` or `confirm()` anywhere.
  - Do NOT use a toast for success — the modal simply closes and the list re-renders.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — form + modal + validation.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 4)
  - **Blocks**: T19
  - **Blocked By**: T1, T2, T6, T14

  **References**:
  - T6 (parseAmountInput, formatAmount), T14 (stores).
  - WAI-ARIA dialog (minimum): `https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/` — at minimum `role="dialog"` and `aria-modal="true"`.

  **Acceptance Criteria**:
  - [ ] In Add mode, all four fields are empty/default; on submit with valid data, an expense appears in the store
  - [ ] In Edit mode, fields are pre-filled; on submit, the existing expense is updated (id unchanged)
  - [ ] Invalid submit shows inline errors; no store mutation occurs
  - [ ] Esc closes; backdrop click closes; Cancel closes
  - [ ] Mobile viewport: dialog is full-screen-comfortable

  **QA Scenarios**:
  ```
  Scenario: Add expense end-to-end (happy)
    Tool: Playwright (entry via dashboard — see T19)
    Steps:
      1. goto /; click + Add expense
      2. fill amount-input '42.50', date-input '2026-01-15', select first category option (not Uncategorized), note-input 'lunch'
      3. click modal-submit
      4. expect modal closed; expense-row count incremented by 1; first row contains '42.50' and 'lunch'
      5. screenshot: .omo/evidence/task-16-add-success.png
    Expected Result: row added at top (newest first)
    Evidence: .omo/evidence/task-16-add-success.png

  Scenario: Validation rejects bad amount (negative path)
    Tool: Playwright
    Steps:
      1. open modal; fill amount-input '-5'; click submit
      2. expect [data-testid="amount-error"] visible; modal still open; no new expense
      3. screenshot: .omo/evidence/task-16-validation.png
    Expected Result: error visible, modal persists
    Evidence: .omo/evidence/task-16-validation.png

  Scenario: Edit pre-fills + updates (happy)
    Tool: Playwright
    Steps:
      1. goto /; capture first row's data-expense-id and amount
      2. click that row's expense-edit-btn → modal opens, amount-input value === captured amount
      3. clear amount-input; type '99.00'; submit
      4. expect modal closed; that row's displayed amount === '99.00'; expense-row count unchanged
      5. screenshot: .omo/evidence/task-16-edit-success.png
    Expected Result: edit reflected; no new row created
    Evidence: .omo/evidence/task-16-edit-success.png

  Scenario: Escape and backdrop close
    Tool: Playwright
    Steps:
      1. Open modal; press Escape → closed
      2. Open modal; click modal-backdrop → closed
      3. record both outcomes to .omo/evidence/task-16-dismiss.json
    Expected Result: both dismiss paths close the modal
    Evidence: .omo/evidence/task-16-dismiss.json
  ```

  **Evidence to Capture**:
  - [ ] `task-16-add-success.png`
  - [ ] `task-16-validation.png`
  - [ ] `task-16-edit-success.png`
  - [ ] `task-16-dismiss.json`

  **Commit**: YES — `feat(components): expense add/edit modal with native validation`. Files: `src/lib/components/ExpenseFormModal.svelte`. Pre-commit: `npx tsc --noEmit && npx svelte-check`.

- [x] 17. **Monthly bar chart** — `src/lib/components/MonthlyBarChart.svelte`

  **What to do**:
  - `src/lib/components/MonthlyBarChart.svelte`:
    - Imports: `import { browser } from '$app/environment';` + Chart.js + `Bar` from `svelte-chartjs` + `ensureChartJsRegistered`, `chartThemeColors` from `$lib/chart/chartSetup` + `last12MonthKeys`, `monthKey`, `formatMonthLabel` from `$utils/dates` + `expenses` store.
    - Container `<div data-testid="monthly-chart" class="h-64 w-full">` — explicit height is mandatory (Chart.js collapses without it).
    - Inside, gate with `{#if browser}` so the chart only mounts in the browser.
    - On mount (inside browser branch): `ensureChartJsRegistered()`.
    - Compute data reactively:
      - `const keys = last12MonthKeys();`
      - Bucket `$expenses` into 12 totals keyed by `monthKey(e.date)`; missing months are `0`.
      - Labels: `keys.map(formatMonthLabel)`.
      - Single dataset; bar color: `chartThemeColors(isDark).legend` (or a single accent — `#3b82f6` is fine since this chart has no per-category split).
    - Theme awareness: subscribe to `document.documentElement.classList` for the `dark` class via a `MutationObserver` (cleanly disposed on destroy), update Chart.js `options.scales.x.ticks.color`, `options.scales.y.ticks.color`, `options.scales.{x,y}.grid.color`, `options.plugins.legend.labels.color` accordingly when the dark class flips. Re-render via `chart.update()`. (The Bar component from svelte-chartjs handles re-renders on data/options change reactively — verify with the wrapper's docs.)
    - Chart options: `responsive: true`, `maintainAspectRatio: false`, `plugins.legend.display: false` (it's a single-series chart), `scales.y.beginAtZero: true`.

  **Must NOT do**:
  - Do NOT disable SSR for the parent route (use `{#if browser}` instead).
  - Do NOT register Chart.js at module top level (use `ensureChartJsRegistered` inside the browser branch).
  - Do NOT hardcode the 12 month labels — derive at render time.
  - Do NOT compute totals from a `derived` store (per Metis directive — single component using it).

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — chart integration + theme reactivity.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES with T18 (Wave 5)
  - **Blocks**: T19
  - **Blocked By**: T1, T2, T5, T7, T14

  **References**:
  - T5 (`last12MonthKeys`, `monthKey`, `formatMonthLabel`), T7 (`ensureChartJsRegistered`, `chartThemeColors`), T14 (`expenses` store).
  - svelte-chartjs docs for the `<Bar>` component.
  - Chart.js Bar config: `https://www.chartjs.org/docs/latest/charts/bar.html`.

  **Acceptance Criteria**:
  - [ ] Container has `data-testid="monthly-chart"` and Tailwind class for explicit height (`h-64` or similar)
  - [ ] When empty (zero expenses), all 12 bars render at height 0; canvas remains visible (no collapse)
  - [ ] When expenses are added, the corresponding month's bar updates immediately
  - [ ] Theme toggle re-colors tick labels and grid lines (not stuck on default Chart.js gray)
  - [ ] No SSR errors (`npm run build` does not warn about `window is not defined`)

  **QA Scenarios**:
  ```
  Scenario: 12 bars present, including zero-filled months (Playwright)
    Tool: Playwright
    Steps:
      1. seed expense store with expenses in only 3 distinct months
      2. goto /
      3. await page.waitForSelector('[data-testid="monthly-chart"] canvas');
      4. evaluate via window: read the chart instance's data.labels and data.datasets[0].data
      5. assert labels.length === 12; data.length === 12; exactly 3 non-zero entries
      6. screenshot: .omo/evidence/task-17-bars-12.png
    Expected Result: 12 labels, 12 values, 3 non-zero
    Evidence: .omo/evidence/task-17-bars-12.png, .omo/evidence/task-17-bars-data.json

  Scenario: Theme reactivity
    Tool: Playwright
    Steps:
      1. goto /; capture chart options.scales.x.ticks.color (via window-exposed chart instance)
      2. click theme-toggle; wait 200ms; capture again
      3. assert colors differ
      4. screenshot before + after: .omo/evidence/task-17-theme-{light,dark}.png
    Expected Result: tick color changes between modes
    Evidence: .omo/evidence/task-17-theme-light.png, task-17-theme-dark.png, task-17-theme-colors.json

  Scenario: SSR build doesn't reference window
    Tool: Bash
    Steps:
      1. npm run build 2>&1 | tee .omo/evidence/task-17-build.txt
      2. grep -i "window is not defined" .omo/evidence/task-17-build.txt && echo FAIL || echo OK >> .omo/evidence/task-17-build.txt
    Expected Result: "OK"
    Evidence: .omo/evidence/task-17-build.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-17-bars-12.png`, `task-17-bars-data.json`
  - [ ] `task-17-theme-light.png`, `task-17-theme-dark.png`, `task-17-theme-colors.json`
  - [ ] `task-17-build.txt`

  **Commit**: YES — `feat(charts): trailing-12-month bar chart with theme awareness`. Files: `src/lib/components/MonthlyBarChart.svelte`. Pre-commit: `npx tsc --noEmit && npx svelte-check && npm run build`.

- [x] 18. **Category breakdown doughnut chart** — `src/lib/components/CategoryDoughnutChart.svelte`

  **What to do**:
  - `src/lib/components/CategoryDoughnutChart.svelte`:
    - Similar shell to T17: `{#if browser}` guard, `ensureChartJsRegistered`, explicit-height container `data-testid="category-chart"` `class="h-64 w-full"`.
    - Reactive computation:
      - Group `$expenses` by `categoryId`; sum each group's `amount`; drop categories with `total === 0` (don't render empty slices).
      - For each remaining group, look up the category in `$categories` for `name` and `color`.
      - Datasets: single Doughnut with `data: totals`, `backgroundColor: colors`, `labels: names`.
    - Options: `responsive: true`, `maintainAspectRatio: false`, `plugins.legend.position: 'right'` on desktop and `'bottom'` on mobile (Tailwind responsive class on the wrapper or a `matchMedia` check inside `options` — pick one and document the choice).
    - Theme reactivity: legend label colors use `chartThemeColors(isDark).legend`.
    - Empty fallback: if `$expenses.length === 0`, render a small placeholder text inside the chart container (NOT a separate component): `<p class="text-sm text-gray-500 dark:text-gray-400">No expenses yet — chart will populate as you add them.</p>`.

  **Must NOT do**:
  - Do NOT include categories with zero total (avoid useless tooltip noise).
  - Do NOT hardcode category-to-color mappings — pull from `category.color` (which itself came from `colorForCategoryId` or user override).
  - Do NOT exceed the two-chart cap (no extra trend lines, no inset, etc.).
  - Do NOT disable SSR for the route.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — chart with reactive aggregation.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES with T17 (Wave 5)
  - **Blocks**: T19
  - **Blocked By**: T1, T2, T4, T7, T14

  **References**:
  - T4 (color), T7 (register/theme helpers), T14 (stores).
  - svelte-chartjs `<Doughnut>` component.

  **Acceptance Criteria**:
  - [ ] Container has `data-testid="category-chart"` and explicit height
  - [ ] Renders one slice per category that has at least one expense (post-cascade behavior)
  - [ ] Empty-expense state shows the placeholder text inside the same container
  - [ ] Theme toggle re-colors legend labels
  - [ ] Category color override (via T20) reflects in the slice color

  **QA Scenarios**:
  ```
  Scenario: Doughnut reflects current category distribution
    Tool: Playwright
    Steps:
      1. seed with 4 expenses across 3 distinct categories
      2. goto /; read chart instance: data.labels.length === 3, data.datasets[0].data.length === 3
      3. add a 5th expense to a 4th category → labels.length becomes 4
      4. screenshot before & after: .omo/evidence/task-18-doughnut-{before,after}.png
    Expected Result: dynamic update on add
    Evidence: .omo/evidence/task-18-doughnut-before.png, -after.png, -data.json

  Scenario: Color override propagates
    Tool: Playwright
    Steps:
      1. Visit /categories; edit one category, set color via the color input to '#ff00ff'; save
      2. Visit /; read that slice's backgroundColor from the chart instance
      3. assert it equals '#ff00ff' (or rgb(255,0,255) — normalize)
      4. screenshot: .omo/evidence/task-18-color-override.png
    Expected Result: chart slice matches the user-chosen color
    Evidence: .omo/evidence/task-18-color-override.png

  Scenario: Zero-expense placeholder
    Tool: Playwright
    Steps:
      1. seed empty expenses
      2. goto /; assert [data-testid="category-chart"] contains text "chart will populate"
      3. screenshot: .omo/evidence/task-18-empty.png
    Expected Result: placeholder visible
    Evidence: .omo/evidence/task-18-empty.png
  ```

  **Evidence to Capture**:
  - [ ] `task-18-doughnut-before.png`, `-after.png`, `-data.json`
  - [ ] `task-18-color-override.png`
  - [ ] `task-18-empty.png`

  **Commit**: YES — `feat(charts): category doughnut with color override + empty placeholder`. Files: `src/lib/components/CategoryDoughnutChart.svelte`. Pre-commit: `npx tsc --noEmit && npx svelte-check && npm run build`.

- [x] 19. **Dashboard route — `/`** — `src/routes/+page.svelte`

  **What to do**:
  - `src/routes/+page.svelte`:
    - Composes the dashboard:
      - Top of content area: a horizontal flex row with a heading `Expenses` on the left and a `+ Add expense` button (`data-testid="add-expense-btn"`) on the right.
      - Two-column grid for the charts on desktop, stacked on mobile: `class="grid grid-cols-1 lg:grid-cols-2 gap-4"`. First child `<MonthlyBarChart />`, second `<CategoryDoughnutChart />`.
      - Below: `<ExpenseList />`.
      - At the very bottom (or appended once): `<ExpenseFormModal bind:open={modalOpen} expense={editingExpense} on:close={closeModal} />`.
    - State: `let modalOpen = false; let editingExpense: Expense | undefined = undefined;`
      - Add button click: `editingExpense = undefined; modalOpen = true;`
      - List edit event: `editingExpense = event.detail; modalOpen = true;`
      - On modal close: `modalOpen = false; editingExpense = undefined;`
    - On mount: `refreshExpenses(); refreshCategories();` (idempotent).
    - No `+page.server.ts` and no `+page.ts` `load` — all client-side.

  **Must NOT do**:
  - Do NOT create a `+page.server.ts`.
  - Do NOT add filter/sort/pagination/search UI.
  - Do NOT add a third chart.
  - Do NOT mount the modal as a child of the list (sibling-only, to avoid weird scroll-trap interactions).

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — composition + small state.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO — this is the final dashboard integration after charts are complete
  - **Blocks**: F1–F4
  - **Blocked By**: T13, T15, T16, T17, T18

  **References**:
  - T15 (ExpenseList), T16 (ExpenseFormModal), T17 (MonthlyBarChart), T18 (CategoryDoughnutChart).
  - Tailwind responsive grid: `https://tailwindcss.com/docs/grid-template-columns`.

  **Acceptance Criteria**:
  - [ ] `/` renders heading + Add button + 2 charts (or empty-placeholder for doughnut) + expense list
  - [ ] Clicking `+ Add expense` opens the modal in Add mode
  - [ ] Clicking ✎ on any row opens the modal in Edit mode with that expense
  - [ ] Modal close returns to the dashboard with the list updated
  - [ ] On mobile, both charts stack vertically; the add button is reachable

  **QA Scenarios**:
  ```
  Scenario: Full add-expense flow from dashboard
    Tool: Playwright
    Steps:
      1. goto /
      2. screenshot: .omo/evidence/task-19-initial.png
      3. click [data-testid="add-expense-btn"]
      4. fill in modal (amount 12.34, today's date, first non-uncat category, note 'test')
      5. submit
      6. expect modal closed; new row at top contains 12.34
      7. monthly chart total for current month bar increased
      8. screenshot: .omo/evidence/task-19-after-add.png
    Expected Result: end-to-end flow works
    Evidence: .omo/evidence/task-19-initial.png, .omo/evidence/task-19-after-add.png

  Scenario: Mobile dashboard layout
    Tool: Playwright
    Steps:
      1. setViewportSize 375x667; goto /
      2. capture chart container ordering: both charts visible, stacked vertically (lg:grid-cols-2 collapses to grid-cols-1)
      3. screenshot: .omo/evidence/task-19-mobile.png
    Expected Result: stacked layout, no horizontal scroll
    Evidence: .omo/evidence/task-19-mobile.png

  Scenario: No +page.server.ts in route (negative)
    Tool: Bash
    Steps:
      1. test ! -f src/routes/+page.server.ts && echo OK || echo FAIL > .omo/evidence/task-19-no-server.txt
    Expected Result: "OK"
    Evidence: .omo/evidence/task-19-no-server.txt
  ```

  **Evidence to Capture**:
  - [ ] `task-19-initial.png`, `task-19-after-add.png`, `task-19-mobile.png`, `task-19-no-server.txt`

  **Commit**: YES — `feat(dashboard): compose list + charts + add modal`. Files: `src/routes/+page.svelte`. Pre-commit: `npx tsc --noEmit && npx svelte-check && npm run build`.

- [x] 20. **Categories route — `/categories`** — `src/routes/categories/+page.svelte`

  **What to do**:
  - `src/routes/categories/+page.svelte`:
    - Heading: `Categories`.
    - Add category form (inline at top): single-row form with name input (`data-testid="new-category-name"`), color input (`<input type="color">` with `data-testid="new-category-color"`, default to a hash-derived value via `colorForCategoryId(crypto.randomUUID())`), and Add button (`data-testid="new-category-submit"`). Validation: name required, name ≤ 50 chars, not a duplicate (case-insensitive). Inline error under the form with `data-testid="new-category-error"`.
    - Category list below: each entry shows the color swatch + name + (for non-Uncategorized) edit and delete controls. Each row has `data-testid="category-row"`, `data-category-id={category.id}`. Uncategorized's row shows no delete button (`data-testid="category-uncategorized"`).
    - Edit flow: clicking ✎ on a row switches that row to inline-edit mode — name input + color input + Save / Cancel buttons inline. Save calls `editCategory`; Cancel reverts. Validation same as Add.
    - Delete flow: clicking 🗑 switches to inline confirm — `Delete` (red) + `Cancel`. Confirming triggers `deleteCategoryWithCascade(id)` which reassigns expenses to Uncategorized. After success, show a small inline notice for ~5 seconds: `"N expenses moved to Uncategorized"` (`data-testid="cascade-notice"`).
    - On mount: `refreshCategories(); refreshExpenses();` (the latter so the cascade count is correct).
    - Empty state for the list is impossible (Uncategorized always exists) — no empty-state UI needed.

  **Must NOT do**:
  - Do NOT add a delete button to the Uncategorized row.
  - Do NOT use a toast library for the cascade notice — inline element only.
  - Do NOT separate the edit form into a different page or modal — inline-edit-in-row only.
  - Do NOT add a color picker library — `<input type="color">` is built-in.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — composite CRUD page.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES with T17 and T18 (Wave 5)
  - **Blocks**: F1–F4
  - **Blocked By**: T2, T4, T13, T14

  **References**:
  - T4 (colorForCategoryId), T14 (categories store + deleteCategoryWithCascade).
  - `<input type="color">` MDN: `https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/color`.

  **Acceptance Criteria**:
  - [ ] Page lists 6 default categories on first load; Uncategorized first
  - [ ] Add form: valid name → new row appears; the same name appears in the expense form's category dropdown on `/`
  - [ ] Edit name + color → row updates; the doughnut chart on `/` re-colors the affected slice on next visit
  - [ ] Delete a non-Uncategorized category → row removed; expenses with that categoryId now show "Uncategorized" on `/`; inline notice visible with correct count
  - [ ] Uncategorized row: NO delete button visible
  - [ ] Attempting to add a duplicate name → inline error; no row added

  **QA Scenarios**:
  ```
  Scenario: Add → Edit → Delete with cascade (happy)
    Tool: Playwright
    Steps:
      1. goto /categories
      2. fill new-category-name 'Coffee', leave default color, click new-category-submit → new row appears with 'Coffee'
      3. screenshot: .omo/evidence/task-20-add.png
      4. goto /; open Add expense modal; choose 'Coffee'; submit (amount 4.50)
      5. goto /categories; click ✎ on Coffee row; change color to '#aa00ff'; save
      6. screenshot: .omo/evidence/task-20-edit.png
      7. click 🗑 on Coffee row → confirm → click Delete
      8. expect cascade-notice visible with text "1 expense moved to Uncategorized"
      9. screenshot: .omo/evidence/task-20-cascade.png
      10. goto /; assert the expense (4.50) now displays "Uncategorized" as category
    Expected Result: full lifecycle works; cascade message accurate
    Evidence: task-20-add.png, task-20-edit.png, task-20-cascade.png

  Scenario: Uncategorized is immutable (negative)
    Tool: Playwright
    Steps:
      1. goto /categories
      2. locate [data-testid="category-uncategorized"]
      3. assert NO descendant [data-testid="category-delete-btn"]
      4. attempt edit → name input should be disabled OR submit should reject with VALIDATION error from repo
      5. record assertions to .omo/evidence/task-20-immutable.json
    Expected Result: cannot delete; cannot rename
    Evidence: .omo/evidence/task-20-immutable.json

  Scenario: Duplicate name rejected (negative)
    Tool: Playwright
    Steps:
      1. goto /categories
      2. submit Add form with name 'Food'
      3. expect [data-testid="new-category-error"] visible
      4. screenshot: .omo/evidence/task-20-duplicate.png
    Expected Result: error visible; no new row
    Evidence: .omo/evidence/task-20-duplicate.png

  Scenario: Mobile category page layout
    Tool: Playwright
    Steps:
      1. setViewportSize 375x667; goto /categories
      2. screenshot: .omo/evidence/task-20-mobile.png
      3. assert no horizontal scroll
    Expected Result: usable on mobile
    Evidence: .omo/evidence/task-20-mobile.png
  ```

  **Evidence to Capture**:
  - [ ] `task-20-add.png`, `task-20-edit.png`, `task-20-cascade.png`
  - [ ] `task-20-immutable.json`
  - [ ] `task-20-duplicate.png`
  - [ ] `task-20-mobile.png`

  **Commit**: YES — `feat(categories): manage page with inline edit + cascade delete`. Files: `src/routes/categories/+page.svelte`. Pre-commit: `npx tsc --noEmit && npx svelte-check && npm run build`.

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and wait for explicit "okay" before completing.
>
> **Never mark F1–F4 as checked before user approval.** Rejection or user feedback → fix → re-run → present again → wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`

  Read this plan end-to-end (`.omo/plans/expense-tracker-webui.md`). For each "Must Have": verify the implementation exists by reading the relevant file, running the relevant command, or invoking the relevant DOM via Playwright. For each "Must NOT Have": search the codebase for the forbidden pattern (e.g., `grep -r "alert("`, `grep -r "@apply" src/`, `ast-grep` for `<Button>`/`<Modal>`/`<Card>` component wrappers, `grep -r "+page.server"`, etc.) — reject with file:line if any forbidden pattern is found. Verify all `.omo/evidence/` files exist and are non-empty. Compare deliverables against this plan's "Concrete Deliverables" list.

  **Acceptance Criteria**:
  - [ ] Every Must Have item is marked present with file/command/DOM evidence
  - [ ] Every Must NOT Have item is marked absent, or rejected with exact file:line citation
  - [ ] Evidence files exist for every task T1–T20 and every final integration flow
  - [ ] Output verdict is `APPROVE` only if all checks pass; otherwise `REJECT` with blocking citations

  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | Evidence [N/N] | VERDICT: APPROVE/REJECT (with file:line citations if REJECT)`

- [x] F2. **Code Quality Review** — `unspecified-high`

  Run `npx tsc --noEmit` (full project), `npx svelte-check`, `npm run build`, and `npx playwright test`. Manually review every changed file under `src/` for: `as any`, `@ts-ignore`, `@ts-expect-error`, empty catch blocks, `console.log`/`console.debug`/`console.info` calls, commented-out code blocks, unused imports, unused variables. AI-slop scan: excessively long comments restating obvious code, over-abstraction (a `<Button>` wrapper that just forwards props, a generic `createRepo<T>` factory), generic names (`data`, `result`, `item`, `temp`, `handler` without context).

  **Acceptance Criteria**:
  - [ ] `npx tsc --noEmit` exits 0
  - [ ] `npx svelte-check --threshold error` exits 0
  - [ ] `npm run build` exits 0 with no SSR `window is not defined` errors
  - [ ] `npx playwright test` exits 0
  - [ ] Manual review finds no forbidden TypeScript suppressions, console logs, commented-out code, empty catches, or AI-slop abstractions
  - [ ] Output verdict is `APPROVE` only if all checks pass; otherwise `REJECT` with exact file:line citations

  Output: `Build [PASS/FAIL] | tsc [PASS/FAIL] | svelte-check [N errors / N warnings] | Playwright [N pass / N fail] | Files [N clean / N issues] | VERDICT: APPROVE/REJECT`

- [x] F3. **Real Manual QA via Playwright** — `unspecified-high` (with `playwright` skill)

  Start from a clean state (`rm -rf node_modules/.vite .svelte-kit && npm run dev`). Open Playwright and execute EVERY QA scenario from EVERY task in sequence — follow the exact steps, capture evidence into `.omo/evidence/final-qa/task-{N}-{scenario-slug}.{png|json|txt}`. Then run cross-task integration flows: (1) add 3 expenses with different categories → both charts update → delete one category → those expenses reassign to Uncategorized → doughnut updates; (2) toggle dark mode mid-session → chart text/grid colors update correctly → reload → mode persists; (3) on mobile viewport (375×667), exercise the full add-expense flow → modal is full-screen-friendly → list scrolls → nav collapses. Edge cases: empty list state, all-zero months bar chart, deleting all custom categories down to just Uncategorized, attempting to delete Uncategorized (UI must hide the button; repo must throw).

  **Acceptance Criteria**:
  - [ ] Every task QA scenario from T1–T20 is executed and has matching evidence under `.omo/evidence/final-qa/`
  - [ ] All 3 integration flows pass exactly as specified
  - [ ] Empty state, zero-month chart, all-custom-categories-deleted, and Uncategorized-immutable edge cases pass
  - [ ] Mobile viewport 375×667 has no horizontal scroll and all core flows remain usable
  - [ ] Output verdict is `APPROVE` only if every scenario passes; otherwise `REJECT` with failing step + screenshot/evidence path

  Output: `Per-task scenarios [N/N pass] | Integration flows [3/3] | Edge cases [N/N tested] | Mobile [PASS/FAIL] | VERDICT: APPROVE/REJECT`

- [x] F4. **Scope Fidelity Check** — `deep`

  For each task T1–T20: read the "What to do" + "Must NOT do" sections in this plan, then read the actual diff via `git log --all --diff-filter=A --name-only` and `git diff <pre-implementation>..HEAD`. Verify a 1:1 mapping — every spec item was built (nothing missing) and nothing beyond spec was built (no scope creep / no AI slop). Detect cross-task contamination (e.g., T15 touching files owned by T16). Flag any files in `src/` that aren't accounted for by some task. Verify the repository interface methods are exactly what the UI uses — no speculative `findByX`, no unused parameters beyond the explicitly future-proofed `{ limit?, offset? }` on `list()`.

  **Acceptance Criteria**:
  - [ ] Every changed source/config file is attributable to exactly one task or explicitly shared setup from T1
  - [ ] Every task's "What to do" bullets are implemented, or rejected with exact missing item(s)
  - [ ] Every task's "Must NOT do" bullets are respected, or rejected with exact file:line citation
  - [ ] No unplanned routes, features, dependencies, or UI surfaces exist
  - [ ] Repository interface surface matches this plan exactly (no speculative methods)
  - [ ] Output verdict is `APPROVE` only if implementation is 1:1 with the plan; otherwise `REJECT` with diff/file citations

  Output: `Tasks [N/N compliant] | Contamination [CLEAN / N issues] | Unaccounted files [CLEAN / N files] | Speculative API surface [CLEAN / N issues] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

- One commit per task using Conventional Commits.
- Format: `<type>(scope): <description>` — example: `feat(expense-list): inline delete with row-level confirm`
- Allowed types: `feat`, `fix`, `chore`, `refactor`, `test`, `style`, `docs`
- Pre-commit per task: run `npx tsc --noEmit` and `npx svelte-check` — must be clean.
- Final verification wave tasks F1–F4 do NOT produce commits; they produce reports under `.omo/evidence/final-qa/`.

---

## Success Criteria

### Verification Commands

```bash
cd /Users/grant/dev/quid/webui

# Type & lint integrity
npx tsc --noEmit                                # Expected: 0 errors
npx svelte-check --threshold error              # Expected: 0 errors

# Build integrity
npm run build                                   # Expected: build succeeds, no warnings about SSR-incompatible imports

# Test integrity
npx playwright test                             # Expected: all specs pass

# Guardrail verification (sample — F1 does the exhaustive sweep)
! grep -r "alert(" src/ 2>/dev/null              # Expected: no matches
! grep -r "+page.server" src/ 2>/dev/null        # Expected: no matches
! grep -rE "(as any|@ts-ignore|@ts-expect-error)" src/ 2>/dev/null  # Expected: no matches
! grep -rE "@apply" src/ 2>/dev/null | grep -v "app.css.*body" # Expected: only the body dark-bg line

# Runtime smoke
npm run dev &                                   # Starts dev server
sleep 5
curl -sf http://localhost:5173/ > /dev/null     # Expected: 200 OK
curl -sf http://localhost:5173/categories > /dev/null  # Expected: 200 OK
```

### Final Checklist

- [ ] All "Must Have" items present (verified by F1)
- [ ] All "Must NOT Have" items absent (verified by F1's grep/ast-grep sweep)
- [ ] All Playwright specs green (verified by F2)
- [ ] All per-task QA scenarios executed with evidence captured (verified by F3)
- [ ] No scope creep / no cross-task contamination (verified by F4)
- [ ] User has explicitly said "okay" after reviewing F1–F4 results
