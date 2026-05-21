## 2026-05-20 Task: orchestration-init
- No implementation issues observed yet.

## 2026-05-20 Task: scaffold-webui
- `127.0.0.1:5173` was already serving another app during evidence capture, so the dev-server proof used `--port 4173 --strictPort` to avoid the collision.
- Generated `/demo` routes and the demo Playwright test were removed as scaffold noise to satisfy the final route scope.

## 2026-05-21 Task: domain-types
- No issues encountered.

## 2026-05-21 Task: repository-interfaces
- Atlas caught and fixed the pagination and `RepositoryError` constructor contract mismatch.

## 2026-05-21 Task: tailwind-dark-mode-bootstrap
- Atlas caught an empty `catch (e) {}` in the `src/app.html` pre-paint script; fixed by falling back to removing the `dark` class so storage/matchMedia errors degrade to light mode without silent swallowing.
- Atlas LSP also flagged `noInnerDeclarations` on `var stored/dark`, `useArrowFunction` on the `function () {}` IIFE, and an unused `catch (e)` binding; refactored to an arrow IIFE with `let` declarations and bindingless `catch {}` keeping behavior identical.
- Atlas re-checked plan: T8 acceptance expects `src/app.css` imported from `+layout.svelte` via `../app.css`. The scaffold default of `src/routes/layout.css` was relocated to `src/app.css`; old file removed and import path updated. Tailwind v4 syntax (`@import 'tailwindcss';` + `@custom-variant dark`) preserved since `@tailwind base/components/utilities` is not the v4 entrypoint for this scaffold.

## 2026-05-21 Task: money-formatter
- Atlas caught the initial implementation exporting only `formatMoney`; the plan actually needs `formatAmount` plus `parseAmountInput`, so the helper was corrected to match the checklist exactly.

## 2026-05-21 Task: chart-setup-module
- Atlas caught the initial top-level `Chart.register(...registerables)` mismatch; the module now defers registration to `ensureChartJsRegistered()` and keeps the call idempotent.

## 2026-05-21 Task: mock-seed-defaults
- Atlas initially marked T9 at the wrong path/content; the actual plan target is `src/lib/repos/seed.ts` with runtime-dated sample expenses, and the seed module was corrected to match.

## 2026-05-21 Task: writable-stores-cascade
- No issues encountered.

## 2026-05-21 Task: expense-form-modal (T16) — review fixes
- First pass diverged from plan: used `onClose` callback only (no Svelte `close` event), `type="text"` + `inputmode="decimal"` amount, `<textarea>` note, and `cancel-button`/`submit-button` test IDs. Fixed in commit aa3dccd by switching to `createEventDispatcher<{ close: void }>()`, `<input type="number" step="0.01" min="0">` amount (value/oninput pattern preserves the string pipeline for `parseAmountInput`), `<input type="text" maxlength="200">` note, and `modal-cancel`/`modal-submit` test IDs.
- Mobile/desktop split now uses Tailwind `sm:` breakpoint: backdrop is edge-to-edge with no padding under 640px, dialog is `h-full w-full` (no rounded corners, no max-w) on mobile and snaps to centered `max-w-md` rounded card at `sm:` and up. Footer uses `mt-auto` so Cancel/Save sit at the bottom on full-screen mobile and tight under the form on desktop.
- `createEventDispatcher` is technically deprecated in Svelte 5 runes mode but still functional and svelte-check 4.4.6 emits no warnings; chose it over a callback prop to literally satisfy the plan's "dispatch close event" wording.
