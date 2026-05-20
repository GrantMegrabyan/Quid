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

## 2026-05-21 Task: money-formatter
- Atlas caught the initial implementation exporting only `formatMoney`; the plan actually needs `formatAmount` plus `parseAmountInput`, so the helper was corrected to match the checklist exactly.

## 2026-05-21 Task: chart-setup-module
- Atlas caught the initial top-level `Chart.register(...registerables)` mismatch; the module now defers registration to `ensureChartJsRegistered()` and keeps the call idempotent.
