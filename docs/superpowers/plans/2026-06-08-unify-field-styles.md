# Unify Field / Select Styling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the copy-pasted inline Tailwind class strings on every standard form input/select/textarea in the webui with two shared component classes (`.field`, `.field-select`), giving selects a custom chevron so they visually match text inputs.

**Architecture:** Add a `@layer components` block to `webui/src/app.css` defining `.field` (the canonical input style) and `.field-select` (adds `appearance-none` + a custom SVG chevron). Then sweep each route/component, swapping the inline class soup for `field` / `field field-select` while preserving genuine per-instance modifiers (`w-full`, `resize-y`, `font-mono`, icon padding, `disabled:opacity-*`). Deliberately compact/special inputs (checkboxes, file inputs, the import preview conditional-error editor, the Amazon in-card pill editors) are left untouched.

**Tech Stack:** SvelteKit, Tailwind CSS v4 (`@import 'tailwindcss'`, `@theme` tokens, `@layer components`, `@apply`), Catppuccin-style `ctp-*` color variables, Playwright e2e.

---

## Canonical values (reference for all tasks)

The dominant existing field style (used ~22 times) is the canonical look:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none
```

`.field` encodes exactly that. `.field-select` adds `appearance-none pr-9` plus a chevron background image stroked in `--ctp-overlay1` (`#9ca3af`).

**Intended normalizations (these are deliberate visual changes, not regressions):**
- Settings page fields move from `rounded-lg bg-ctp-surface0` → `rounded-md bg-ctp-base`.
- Rules-page text inputs gain `text-sm` (they were unstyled `text-base`).
- All selects/date inputs lose their stray `h-10`; height is now uniform via `py-2`, matching sibling text inputs.
- Dashboard group-by select moves from `py-1.5 bg-ctp-surface0` → canonical.

**Deliberately EXCLUDED (do NOT touch):**
- Every `type="checkbox"` and `type="file"` input.
- `routes/import/+page.svelte` preview **amount** editor — has a conditional error border (`{row.amountError ? … : …}`) and no accent focus; applying `.field` would fight the error state.
- `routes/amazon/+page.svelte` in-card **category** `<select>` (`rounded-full … px-2 py-0.5 text-xs`) and **short-name** `<input>` (`min-w-0 flex-1 … px-2 py-1`) — intentionally compact inline editors inside order cards.

**Edit mechanics:** Each distinct old class string is unique per file and appears on a single line per element, so single-line class replacements never shift line numbers. Where the SAME old string maps to the SAME new target multiple times in one file, use `Edit` with `replace_all: true`. The one collision (settings: an input and a select share a string but need different targets) is handled with two context-scoped edits.

---

## Task 1: Add `.field` / `.field-select` component classes

**Files:**
- Modify: `webui/src/app.css` (append a `@layer components` block after the base styles, end of file)

- [ ] **Step 1: Add the component classes**

Append to the end of `webui/src/app.css` (after the `body { … }` rule):

```css

/* ── Form field component classes ────────────────────────────────── */
@layer components {
	.field {
		@apply rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none;
	}

	/* Native <select>: drop the browser arrow and draw a custom chevron
	   (stroke = --ctp-overlay1 / #9ca3af) so selects read as proper fields. */
	.field-select {
		@apply appearance-none pr-9;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af' stroke-width='2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 0.75rem center;
		background-size: 1rem 1rem;
	}
}
```

- [ ] **Step 2: Verify the build compiles the new classes**

Run (from `webui/`): `npm run build`
Expected: build succeeds with no Tailwind/PostCSS errors. (`.field`/`.field-select` are unused so far — that is fine; the build still validates the `@apply` directives resolve against the registered `ctp-*` colors.)

- [ ] **Step 3: Commit**

```bash
git add webui/src/app.css
git commit -m "feat(webui): add shared .field/.field-select component classes"
```

---

## Task 2: Migrate the dashboard group-by select + add e2e regression guard

This is the smallest select usage; migrating it first gives us a concrete element to anchor an automated test that proves the chevron migration works.

**Files:**
- Test: `webui/tests/field-styles.e2e.ts` (create)
- Modify: `webui/src/routes/+page.svelte` (the group-by `<select>`, currently around line 270)

- [ ] **Step 1: Write the failing e2e test**

Create `webui/tests/field-styles.e2e.ts`:

```ts
import { expect, test } from '@playwright/test';

// Guards the shared-field migration: a migrated <select> must use the custom
// chevron (appearance:none) and the canonical border color, matching inputs.
test('dashboard group-by select uses the shared field-select style', async ({ page }) => {
	await page.goto('/');

	// The group-by control is the only native <select> on the dashboard and
	// renders unconditionally; target it by its options to stay unambiguous.
	const select = page.locator('select', {
		has: page.locator('option[value="merchant"]')
	});
	await expect(select).toBeVisible();

	// Custom chevron: native appearance removed + a background image set.
	await expect(select).toHaveClass(/field-select/);
	const appearance = await select.evaluate((el) => getComputedStyle(el).appearance);
	expect(appearance).toBe('none');
	const bgImage = await select.evaluate((el) => getComputedStyle(el).backgroundImage);
	expect(bgImage).toContain('url(');
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `webui/`): `npm run test:e2e -- field-styles`
Expected: FAIL — the select does not yet have the `field-select` class / `appearance` is not `none`.

- [ ] **Step 3: Migrate the group-by select**

In `webui/src/routes/+page.svelte`, the group-by `<select>` currently has:

```
class="rounded-lg border border-ctp-surface1 bg-ctp-surface0 px-3 py-1.5 text-sm text-ctp-text"
```

Change its `class` to:

```
class="field field-select"
```

(Leave the dashboard chart-toggle `type="checkbox"` input on line ~240 untouched.)

- [ ] **Step 4: Run the test to verify it passes**

Run (from `webui/`): `npm run test:e2e -- field-styles`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add webui/tests/field-styles.e2e.ts webui/src/routes/+page.svelte
git commit -m "feat(webui): use shared field-select on dashboard group-by; add e2e guard"
```

---

## Task 3: Migrate the Rules page

**Files:**
- Modify: `webui/src/routes/rules/+page.svelte`

The form has three distinct field class strings. Skip the `type="checkbox"` on line ~443.

- [ ] **Step 1: Migrate the plain text/number/date inputs (7 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field
```

(Applies to: name, priority, match-name value, two match-amount values, two match-date inputs.)

- [ ] **Step 2: Migrate the placeholder inputs (2 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none
```

new string:

```
field
```

(Applies to: set-display-name, set-note inputs.)

- [ ] **Step 3: Migrate the selects (4 elements)**

`Edit` with `replace_all: true` — old string:

```
h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field field-select
```

(Applies to: match-name op, match-amount op, action, target-category selects. The `h-10` is intentionally dropped so they match the inputs' height.)

- [ ] **Step 4: Verify no field strings remain & type-check**

Run (from `webui/`):
```bash
grep -n 'focus:border-ctp-accent focus:outline-none' src/routes/rules/+page.svelte
npm run check
```
Expected: grep returns nothing (all field strings migrated); `npm run check` passes.

- [ ] **Step 5: Commit**

```bash
git add webui/src/routes/rules/+page.svelte
git commit -m "feat(webui): use shared field classes on the rules form"
```

---

## Task 4: Migrate the Settings page

**Files:**
- Modify: `webui/src/routes/settings/+page.svelte`

The currency `<select>` and the model `<input>` share an identical old class string but need different targets, so edit each with surrounding context. Skip the three `type="checkbox"` inputs.

- [ ] **Step 1: Migrate the currency select**

`Edit` (unique via the `<select` context) — find:

```
		<select
			bind:value={currency}
			class="rounded-lg border border-ctp-surface1 bg-ctp-surface0 px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none"
```

replace the class value with `field field-select`:

```
		<select
			bind:value={currency}
			class="field field-select"
```

(If the `bind:`/attribute lines differ slightly, match on the `<select … class="rounded-lg …surface0…"` block — it is the only select in the file.)

- [ ] **Step 2: Migrate the model text input**

`Edit` (unique via the `type="text"` model input context) — the remaining occurrence of:

```
class="rounded-lg border border-ctp-surface1 bg-ctp-surface0 px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none"
```

is now only on the model `<input type="text">`. Change that class to:

```
class="field"
```

- [ ] **Step 3: Verify & type-check**

Run (from `webui/`):
```bash
grep -n 'bg-ctp-surface0 px-3 py-2 text-sm text-ctp-text focus' src/routes/settings/+page.svelte
npm run check
```
Expected: grep returns nothing; `npm run check` passes. (The `bg-ctp-surface0/40` card wrappers and the `bg-ctp-surface0` `<code>` chip remain — they are not fields and must stay.)

- [ ] **Step 4: Commit**

```bash
git add webui/src/routes/settings/+page.svelte
git commit -m "feat(webui): use shared field classes on the settings form"
```

---

## Task 5: Migrate the Import page

**Files:**
- Modify: `webui/src/routes/import/+page.svelte`

Migrate: the single-add inputs/selects, the freeform textarea, and the preview-row category/importance selects. **Exclude** the preview **amount** input (conditional error border) and the hidden file input.

- [ ] **Step 1: Migrate the single-add placeholder inputs (3 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none
```

new string:

```
field
```

(Applies to: single Merchant, single Amount, single Note inputs.)

- [ ] **Step 2: Migrate the single-add date input (drop h-10)**

`Edit` — old string:

```
h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field
```

(Single Date input — the only `h-10 …focus:border-ctp-accent` field string in this file.)

- [ ] **Step 3: Migrate the single-add category + importance selects (2 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field field-select
```

(After Step 1–2 this string is unique to the two single-add selects.)

- [ ] **Step 4: Migrate the freeform textarea**

`Edit` — old string:

```
w-full resize-y rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 font-mono text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none
```

new string:

```
field w-full resize-y font-mono
```

- [ ] **Step 5: Migrate the preview-row selects (2 elements)**

`Edit` with `replace_all: true` — old string:

```
h-10 w-full rounded-md border border-ctp-surface1 bg-ctp-base px-3 py-2 text-sm text-ctp-text disabled:opacity-50
```

new string:

```
field field-select h-10 w-full disabled:opacity-50
```

(Preview category + importance selects. `h-10` is kept here so they stay aligned with the sibling preview amount editor, which is excluded and keeps its own `h-10`.)

- [ ] **Step 6: Confirm the excluded amount editor is untouched**

Run (from `webui/`): `grep -n 'row.amountError' src/routes/import/+page.svelte`
Expected: still present — the conditional-error amount `<input>` was NOT migrated.

- [ ] **Step 7: Type-check**

Run (from `webui/`): `npm run check`
Expected: passes.

- [ ] **Step 8: Commit**

```bash
git add webui/src/routes/import/+page.svelte
git commit -m "feat(webui): use shared field classes on the import page"
```

---

## Task 6: Migrate the Amazon page

**Files:**
- Modify: `webui/src/routes/amazon/+page.svelte`

Migrate: the paste-JSON textarea, the search input, and the two filter selects. **Exclude** the file inputs, all checkboxes, the in-card category pill `<select>`, and the in-card short-name `<input>`.

- [ ] **Step 1: Migrate the paste-JSON textarea**

`Edit` — old string:

```
w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 font-mono text-xs text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field w-full font-mono text-xs
```

(`text-xs` overrides the `text-sm` from `.field` because utilities are emitted after the components layer.)

- [ ] **Step 2: Migrate the search input (preserve icon padding)**

`Edit` — old string:

```
w-full rounded-md border border-ctp-surface2 bg-ctp-base py-2 pl-9 pr-3 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none
```

new string:

```
field w-full pl-9 pr-3
```

(`pl-9`/`pr-3` override `.field`'s `px-3` to keep room for the leading search icon.)

- [ ] **Step 3: Migrate the two filter selects (2 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field field-select
```

(After Steps 1–2 this string matches only the two top-of-page filter selects. The in-card category select uses a different `rounded-full … text-xs` string and is left alone.)

- [ ] **Step 4: Confirm the in-card editors are untouched**

Run (from `webui/`):
```bash
grep -n 'amazon-category-select' src/routes/amazon/+page.svelte
grep -n 'amazon-short-name-input' src/routes/amazon/+page.svelte
```
Expected: both still present with their original `rounded-full …`/`min-w-0 flex-1 …` classes (not migrated).

- [ ] **Step 5: Type-check**

Run (from `webui/`): `npm run check`
Expected: passes.

- [ ] **Step 6: Commit**

```bash
git add webui/src/routes/amazon/+page.svelte
git commit -m "feat(webui): use shared field classes on the amazon page"
```

---

## Task 7: Migrate the ExpenseFormModal

**Files:**
- Modify: `webui/src/lib/components/ExpenseFormModal.svelte`

- [ ] **Step 1: Migrate the placeholder text inputs (4 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none
```

new string:

```
field
```

(Applies to: name, amount, note, display-name inputs.)

- [ ] **Step 2: Migrate the date input (drop h-10)**

`Edit` — old string:

```
h-10 rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field
```

- [ ] **Step 3: Migrate the category + importance selects (2 elements)**

`Edit` with `replace_all: true` — old string:

```
rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text focus:border-ctp-accent focus:outline-none
```

new string:

```
field field-select
```

(After Steps 1–2 this string is unique to the two selects.)

- [ ] **Step 4: Verify & type-check**

Run (from `webui/`):
```bash
grep -n 'focus:border-ctp-accent focus:outline-none' src/lib/components/ExpenseFormModal.svelte
npm run check
```
Expected: grep returns nothing; `npm run check` passes.

- [ ] **Step 5: Commit**

```bash
git add webui/src/lib/components/ExpenseFormModal.svelte
git commit -m "feat(webui): use shared field classes on the expense form modal"
```

---

## Task 8: Full verification & browser smoke

No code change unless a defect is found. This is the REQUIRED browser/end-to-end gate from the project's verification policy.

- [ ] **Step 1: Type-check + production build**

Run (from `webui/`):
```bash
npm run check
npm run build
```
Expected: both green.

- [ ] **Step 2: Full e2e suite**

Run (from `webui/`): `npm run test:e2e`
Expected: all pass, including `field-styles.e2e.ts`. (The suite boots its own API on 8001 against `api/.data/quid-e2e.db` and preview on 4173 — safe to run repeatedly.)

- [ ] **Step 3: Browser smoke (agent-browser skill or `npm run dev`)**

For each migrated surface, load the page, watch the network log for any 4xx/5xx, and exercise the controls:
- `/` — open the group-by `<select>`, confirm the custom chevron renders and changing it regroups transactions.
- `/rules` — open the rule form; confirm op/action/category selects show the chevron, are the same height as the text inputs, and submit works.
- `/settings` — confirm currency select + model input render at the canonical `bg-ctp-base` (no leftover `surface0` tint) and a value change persists.
- `/import` — Single-transaction tab (category/importance selects), AI free-form textarea, and the CSV preview category/importance selects; confirm the preview **amount** editor still shows its red error border on invalid input.
- `/amazon` — search input keeps its leading icon, the two filter selects show the chevron, and the in-card category pill / short-name editors are unchanged.
- Dashboard → click a transaction to open `ExpenseFormModal` (edit mode); confirm its inputs and the category/importance selects all match.

Capture and report any console errors. (svelte-chartjs `state_snapshot_uncloneable` warnings on the dashboard are benign and expected — warnings, not errors.)

- [ ] **Step 4: Final consistency sweep**

Run (from `webui/`):
```bash
grep -rn 'rounded-lg border border-ctp-surface1 bg-ctp-surface0 px-3' src
```
Expected: no matches (the settings outlier style is fully gone). Any remaining hit is a missed field — migrate it.

---

## Documentation

No README/AGENTS.md update required: this is a presentation-only change with no new endpoint, CLI command, env var, schema, or user-facing flow. The new `.field`/`.field-select` convention is self-evident in `app.css`; if desired, a one-line note can be added to `webui/README.md` Frontend notes, but it is not mandated by the docs policy.
