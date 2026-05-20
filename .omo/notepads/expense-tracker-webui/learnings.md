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
