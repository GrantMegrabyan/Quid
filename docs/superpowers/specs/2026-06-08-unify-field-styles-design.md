# Unify dropdown/select styling with text inputs

**Date:** 2026-06-08
**Status:** Approved — ready for implementation plan

## Problem

Native `<select>` dropdowns don't visually match text inputs in the webui. Two
issues drive this:

1. **Sizing/color drift** — selects and inputs are styled with inline Tailwind
   class strings that have diverged. The dominant field style (used ~22 times)
   is `rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm
   text-ctp-text focus:border-ctp-accent focus:outline-none`, but the settings
   page is an outlier using `rounded-lg bg-ctp-surface0` (2 occurrences). Some
   selects carry a stray `h-10`, others don't.
2. **No shared style** — there is no canonical field class. Styling is
   copy-pasted inline on every element, so each new field re-drifts.

Goal: one canonical field style, defined once, applied to all native inputs,
selects, and textareas, with selects rendering a **custom chevron** (not the
browser-default arrow) so they read as proper fields.

## Non-goals

- No reusable Svelte `<Field>`/`<Select>` wrapper components (native `<select>`
  + `<option>` slots + `bind:value` make wrapping awkward for no real gain).
- No restyling of buttons, cards, or badges that coincidentally share the
  `rounded-md border …` pattern.
- No backend, schema, API, or behavior changes.

## Environment

- **Tailwind v4** (`@import 'tailwindcss'`, `@theme` tokens, `@custom-variant`).
  Component classes are added via a `@layer components` block using `@apply`.
- `ctp-*` colors are registered Tailwind colors backed by CSS variables
  (`--color-ctp-*` in the `@theme` block), so they are usable inside `@apply`.
- `webui/src/app.css` currently contains only theme tokens + base styles; no
  existing component classes.

## Design

### 1. Component classes in `app.css`

Add a `@layer components` block:

- **`.field`** — shared base for text inputs, textareas, and selects:
  ```css
  @apply rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm
         text-ctp-text placeholder:text-ctp-overlay0
         focus:border-ctp-accent focus:outline-none;
  ```
  The `placeholder:` utility is inert on selects/textareas-without-placeholder,
  so it is safe to keep in the shared base.

- **`.field-select`** — applied in addition to `.field` on selects. Adds
  `appearance-none` and a custom chevron via raw CSS in the same rule:
  - `appearance: none;` (and `-webkit-appearance: none;`) to drop the native
    arrow.
  - `background-image` set to an inline SVG data-URI chevron, stroked in
    `--ctp-overlay1`.
  - `background-repeat: no-repeat;`
  - `background-position: right 0.75rem center;`
  - `background-size: ~1rem;`
  - `padding-right` increased (e.g. `2.25rem`) so option text never overlaps the
    chevron.

Usage:
- text inputs / textareas → `class="field"`
- selects → `class="field field-select"`

Per-instance modifiers (`w-full`, `resize-none`, conditional error borders,
search-icon `pl-9`/`pl-10`, etc.) remain inline alongside the `field` class.

### 2. Migration scope

Replace inline class soup with `.field` / `.field field-select` on every native
input/select/textarea in:

- `routes/rules/+page.svelte` — name/amount/note inputs; match-op & action selects
- `routes/settings/+page.svelte` — currency select, model input (the
  `rounded-lg` / `bg-ctp-surface0` outlier — normalized to canonical)
- `routes/+page.svelte` — group-by select
- `routes/import/+page.svelte` — selects + inputs
- `routes/amazon/+page.svelte` — filter/search selects + inputs
- `lib/components/ExpenseFormModal.svelte` — name/amount/date/note/display-name
  inputs; category & importance selects

Sweep rules:

- Touch only real form fields. Leave buttons, cards, badges alone even if they
  share `rounded-md border …`.
- Preserve per-instance modifiers by keeping them inline next to `field`.
- Where an existing field had a **conflicting** utility (e.g. settings'
  `bg-ctp-surface0`, stray `rounded-lg`, `h-10`), drop it so canonical `.field`
  wins — this normalization is intended.
- Keep leading-icon padding (`pl-9`/`pl-10`) inline on search inputs.

### 3. Verification

- `npm run check` and `npm run build` green.
- **Browser smoke (required by project rules for user-facing changes):** load
  each affected page, confirm no 4xx/5xx in the network log, open every migrated
  select and confirm the custom chevron renders and options select correctly,
  and confirm a text input still shows its placeholder + green focus ring.
  Capture any console errors.
- Spot-check the **settings page** (most-changed fields) and the
  **ExpenseFormModal** (opened in edit mode from the dashboard).
- Run `npm run test:e2e` since multiple user-facing pages change. No e2e
  behavior changes are expected (no new test needed — this is presentation
  only).

### Documentation impact

None. This is a CSS/markup-only change with no new endpoint, CLI command, env
var, schema, or user-facing flow, so no README/AGENTS.md update is required.
The change is committed in one chunk per the commit policy.
