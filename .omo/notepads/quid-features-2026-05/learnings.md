# Learnings

## 2026-05-24 Initial Analysis

### Architecture
- FastAPI + SQLite backend in `api/`, SvelteKit frontend in `webui/`
- Python tooling: `uv`. JS tooling: `npm`
- Alembic migrations in `api/alembic/versions/` - numbered 0001-0004 currently
- Models in `api/src/quid_api/models.py` (SQLAlchemy)
- Schemas in `api/src/quid_api/schemas.py` (Pydantic, camelCase aliases)
- Repositories in `api/src/quid_api/repositories/`
- Routers in `api/src/quid_api/routers/`
- Frontend types in `webui/src/lib/types/domain.ts`
- Frontend repos in `webui/src/lib/repos/`
- Frontend stores in `webui/src/lib/stores/`

### Key Patterns
- All Pydantic schemas use `_Camel` base with `AliasGenerator(to_camel)` - snake_case Python → camelCase JSON
- Expense model: id, name, amount, date, category_id, note (NO display_name yet)
- ImportRule model: supports name/amount/date matching, action=exclude|categorize
- AiRule model: free-text rules sent to AI
- Category model: id, name, color, icon, description
- Icons: hardcoded list of 8 in `categoryIcons.ts` + `CategoryIcon.svelte`
- Lucide icons used via `@lucide/svelte/icons/{name}` imports

### Bug: Transfer Name Modification
- `csv_import.py` line 129-130: `if source_type.lower() == "transfer" and name: name = f"Transfer · {name}"`
- This prepends "Transfer · " to transaction names when CSV has a "type" column with value "Transfer"
- This is WRONG - names should not be modified from CSV

### Input Styling Issue
- Text inputs: `px-3 py-2` with `rounded-md border`
- Selects: same classes but native `<select>` renders shorter
- Fix: add `h-10` to selects to match text input height

### Alembic Migration Pattern
- File naming: `0005_xxx.py`
- revision = "0005", down_revision = "0004"
- Use `op.add_column()` for new columns, `op.create_table()` for new tables

### Frontend Patterns
- Svelte 5 runes syntax ($state, $derived, $effect, $props)
- Tailwind CSS for styling
- Dark mode via `dark:` prefix

## 2026-05-25 Lucide category icon catalog
- `@lucide/svelte` v1.16 exports the canonical icons, an `icons` namespace, aliases, `Icon`, context helpers, and types from its main entry; deriving category icon options from that namespace works in SvelteKit/Vite, but the registry must filter non-icon exports and prefixed/suffixed aliases.
- The full derived picker registry exposed 1,942 selectable keys in browser QA, including previously missing seed keys `car-taxi-front`, `ticket`, and `repeat`.
- `CategoryIcon.svelte` can render a Svelte 5 component variable from the centralized registry, keeping invalid stored values normalized to `circle-help` while letting any derived Lucide key render without adding explicit imports.
- The picker should not render all options at once: keep the empty-query preview small and cap search rendering, with summary text telling users to narrow broad matches.
