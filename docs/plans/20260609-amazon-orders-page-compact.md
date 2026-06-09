# Make the Amazon orders page rows compact (single-line layout)

## Overview

Redesign each Amazon order card on `/amazon` from a tall, two-zone card (left content block + far-right action buttons joined by `justify-between`, which leaves a big empty middle gap on laptop) into a tight, table-like single-line row. Each order collapses to one horizontal line — status indicator, order name, category chip, amount, date/id, and actions — that wraps only when the viewport is narrow. The redesign uses the /frontend-design skill's principles (intentional density, refined spacing, clear hierarchy) while staying inside the existing Catppuccin theme and shared `.field` conventions. No backend, schema, or store changes.

## Context

- Files involved:
  - Modify: `webui/src/routes/amazon/+page.svelte` (only the `{#each $amazonOrders}` row markup, ~lines 879–1131; script logic unchanged)
  - Modify (tests, if needed): `webui/tests/amazon.e2e.ts`
  - Possibly update: `webui/README.md` (Amazon page description, if it describes the row layout)
- Constraints to preserve (pinned by `webui/tests/amazon.e2e.ts`):
  - `data-testid="amazon-order-row"` on each row, and the row must still contain the order-id text (tests `filter({ hasText: '123-4567890-1234567' })`) and the `Linked to …` text.
  - `amazon-link-status` with its `data-link-status="linked|unlinked"` attribute.
  - `amazon-short-name-edit` (button) + `amazon-short-name-input` + a button matching `/save/i` (aria-label "Save name") + a cancel; Enter/Escape handlers.
  - `amazon-order-category` with `data-category-id`, its text (category name / "No category"), the inline `amazon-category-select`, and `amazon-category-edit` pencil.
  - The Find-matches (Search icon) and Delete (Trash) action buttons and the suggestions sub-panel (`Link` buttons) behavior.
- Related patterns: Catppuccin `ctp-*` tokens, `rounded-full` chips, lucide icons already imported, the expense-list row density on the dashboard as a reference for compact rows.
- Dependencies: none new.

## Development Approach

- **Testing approach**: Regular (adjust markup, then run/extend the Playwright e2e suite). This is a layout change with no logic change, so existing e2e tests are the primary guard; browser verification per CLAUDE.md is required.
- Keep all `data-testid`s, aria-labels, and the order-id / "Linked to" text so existing tests pass without weakening assertions.
- Complete each task fully (markup compiles via `npm run check`) before the next.
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Collapse the order row to a single compact line

**Files:**
- Modify: `webui/src/routes/amazon/+page.svelte`

- [x] Replace the row container padding/structure: change the card from `p-4` two-zone (`flex flex-wrap items-start justify-between gap-4` with `min-w-0 flex-1` left block + right actions) to a single horizontal line `flex flex-wrap items-center gap-3` with reduced padding (`px-3 py-2`), keeping the left accent border + linked tint.
- [x] Lay out, left-to-right on one line: (1) compact `amazon-link-status` reduced to an icon-only indicator (Check / Link2Off) keeping `data-testid` and `data-link-status`; (2) order heading `orderHeading(order)` as `truncate min-w-0 flex-1` with the `amazon-short-name-edit` pencil inline; (3) category chip (`amazon-order-category`); (4) amount; (5) date · `order.id` as muted `text-xs` (allowed to truncate/wrap last); (6) the Find-matches + Delete actions pulled inline at the right (no `justify-between` spacer).
- [x] Ensure the line wraps gracefully on narrow widths (flex-wrap) instead of forcing a fixed two-zone split.
- [x] `npm run check` passes (from `webui/`).

### Task 2: Keep inline edit modes and linked/suggestion details compact

**Files:**
- Modify: `webui/src/routes/amazon/+page.svelte`

- [x] Make the short-name edit mode render inline within the compact row (input + save/cancel) without expanding row height excessively; preserve `amazon-short-name-input`, the `/save/i` button, cancel, and Enter/Escape handlers.
- [x] Keep the inline category editor (`amazon-category-select` + cancel) working in the compact row; preserve `amazon-order-category` / `data-category-id` / `amazon-category-edit`.
- [x] Render the `Linked to …` expense line(s) and the unlink button as a compact secondary line under the main row only when linked (preserve the "Linked to" text and unlink aria-label).
- [x] Keep the suggestions sub-panel (`Find matches` results + `Link` buttons) below the row, lightly restyled for consistency.
- [x] `npm run check` passes.

### Task 3: Verify in the browser and update e2e tests

**Files:**
- Modify: `webui/tests/amazon.e2e.ts` (only if a selector/structure assertion needs updating; do not weaken coverage)

- [x] Run `npm run check` and `npm run build` (from `webui/`) — both green.
- [x] Run `npm run test:e2e` (from `webui/`) — the existing Amazon flows (import+link, category edit, short-name edit, recategorise) must pass against the new markup; fix selectors in the page (not the tests) where possible. (All 5 amazon.e2e.ts tests pass against the compact markup; no page selector changes needed.)
- [x] If the icon-only link-status removed asserted text that a test relied on, update the test to assert on the preserved `data-link-status` attribute instead of text (no loss of coverage). (Tests already assert on `data-link-status`; no text-based link-status assertions existed.)
- [x] Capture and confirm no console errors / non-2xx network calls on `/amazon` (load page, edit name, edit category, find matches, link/unlink). (Added a permanent console-error/pageerror guard to the unlink/find-matches/re-link e2e test; passes with zero errors.)

### Task 4: Update documentation

- [ ] Update `webui/README.md` if it describes the Amazon orders row layout to reflect the new compact single-line rows.
- [ ] No AGENTS.md/CLAUDE.md change expected (no new constraint/gotcha); add a one-line note only if a non-obvious layout constraint emerges.
