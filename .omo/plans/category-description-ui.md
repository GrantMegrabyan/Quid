# Category Description UI

## TL;DR

> **Quick Summary**: Expose the existing `Category.description` field in the SvelteKit web UI (Add/Edit forms) and fix the mock category repository to persist it. Backend, migration, schemas, seed, and AI prompt already consume description — this work bridges the frontend UX gap.
>
> **Deliverables**:
> - Description textarea in the Add Category form (between name and color/icon)
> - Description textarea in the Edit Category form (same placement)
> - Add handler sends `description` in POST payload
> - Edit handler sends `description` in PATCH payload
> - `mockCategoryRepository` persists description on create and update; seed entries carry description
>
> **Estimated Effort**: Short
> **Parallel Execution**: YES — 2 waves
> **Critical Path**: Task 1 (reconnaissance) → Task 2 (Add+Edit form edits) ∥ Task 3 (mock repo) → Task 4 (verification) → F1-F4 → user okay

---

## Context

### Original Request
> "For each category I want to add a description. This should be used when making AI call (in the prompt) to better guide the model on which category to use."

### Interview Summary

**Key Discussions**:
- Initial assumption was a full vertical (DB → API → AI → UI). Exploration revealed backend is already 100% implemented.
- Real gap is frontend UI plus a mock repository inconsistency.
- User confirmed strictly two files and a no-tests-just-Playwright-QA approach.

**User Decisions**:
- Scope confirmed: only `+page.svelte` and `mockCategoryRepository.ts`
- Description textarea placed below name, above color/icon
- Optional in UI; empty allowed (matches backend default `""`)
- Leave `Category.description?` optional in `domain.ts`
- Agent-executed Playwright QA only — no formal unit/integration tests

**Research Findings (citations)**:
- `api/src/quid_api/models.py:13-20` — `Category.description: Text, nullable=False, default=""`
- `api/alembic/versions/0004_category_guidance.py:19-27` — column already added (NOT NULL DEFAULT '')
- `api/src/quid_api/schemas.py:33-52` — `CategoryOut/Create/Update` accept `description`
- `api/src/quid_api/routers/categories.py:19-54` — POST/PATCH already accept `description`
- `api/src/quid_api/seed.py:35-126` — all 15 default categories have descriptions
- `api/src/quid_api/routers/expenses.py:150-162, 680-697` — fetches `(Category.name, Category.description)`
- `api/src/quid_api/ai_categorization.py:65-74` — `_format_categories` renders `- Name: Description` (single line, falls back to `- Name`)
- `api/src/quid_api/ai_categorization.py:85-133` — prompt template tells LLM to use descriptions
- `webui/src/lib/types/domain.ts:22-28` — `Category.description?: string`
- `webui/src/lib/repos/seed.ts:22-134` — all 16 categories already have descriptions
- `webui/src/lib/repos/httpCategoryRepository.ts:12-23` — forwards full body, no change needed
- `webui/src/lib/repos/types.ts:51-55` — repo contract uses `Omit<Category, 'id'>` / `Partial<Omit<Category, 'id'>>` so description is type-allowed
- `webui/src/routes/categories/+page.svelte:85-105, 109-165, 220-295, 402-488` — Add/Edit handlers + markup with no description
- `webui/src/lib/repos/mockCategoryRepository.ts:13-34, 43-83` — drops description on create/update

### Metis Review (Gaps Identified & Addressed)

**Critical guardrails** (now codified in Must NOT Have):
- No backend, migration, AI prompt, seed, or `domain.ts`/`httpCategoryRepository.ts` changes
- No description display outside the Add/Edit forms (no list page, no expense picker)
- No new components, character counters, markdown rendering, or validation messages

**Newline correctness**: `<textarea>` accepts newlines but `_format_categories` renders single-line — defaults to collapse `\n` → space on submit (disclosed below).
**Trim policy**: default trim on submit; whitespace-only becomes `""`.
**Explicit key**: always send `description` (never `undefined` / missing) so PATCH semantics are clear.
**Mock seed parity**: mock repo's in-memory seed must carry description on every category so Edit pre-fill never shows literal `"undefined"`.

### Oracle Phase 1 Verdict
**GO (5/5)** — Objective unambiguous, scope explicit, test strategy decided, no outstanding user questions, no contradictions with codebase patterns.

---

## Work Objectives

### Core Objective
Allow users to view and edit each category's `description` from the web UI Add/Edit forms, ensuring the value reaches the API on every create/update and is persisted by both HTTP and mock repositories.

### Concrete Deliverables
- `webui/src/routes/categories/+page.svelte`:
  - Add form: `<textarea>` for description between name and color/icon
  - Edit form: same textarea, pre-filled with current value
  - Both handlers: send `description: <trimmed, newline-collapsed string>` (always, never undefined)
  - Add form reset includes resetting description to `""`
- `webui/src/lib/repos/mockCategoryRepository.ts`:
  - In-memory seed entries: include `description` field (string, defaulting to existing seed values)
  - `create`/`addCategory`: persist `description` from input
  - `update`/`updateCategory`: merge `description` from patch when key is present

### Definition of Done
- [ ] Add form renders a Description textarea; Add submit POSTs `description`
- [ ] Edit form pre-fills with current description; Edit submit PATCHes `description`
- [ ] Mock repo persists description across read-after-write
- [ ] `npm run check` exits 0
- [ ] `npm run build` exits 0
- [ ] All Playwright QA scenarios in this plan pass (evidence in `.omo/evidence/`)
- [ ] No changes to any file outside the two declared targets (verified via `git diff --stat`)

### Must Have
- Description textarea in Add and Edit forms, placed between name and color/icon
- Textarea is optional in UI (empty allowed)
- POST/PATCH bodies always include the `description` key (never `undefined`)
- Newlines collapsed to space on submit (preserves AI prompt single-line rendering in `_format_categories`)
- Whitespace trimmed on submit
- Mock repo: in-memory seed includes description; create/update merge description
- Styling/wrapper pattern matches existing fields in the same file

### Must NOT Have (Guardrails)
- ❌ Touch any file under `api/`
- ❌ Modify `webui/src/lib/types/domain.ts` (keep `description?` optional)
- ❌ Modify `webui/src/lib/repos/seed.ts` (descriptions already present)
- ❌ Modify `webui/src/lib/repos/httpCategoryRepository.ts` (already forwards body)
- ❌ Modify `webui/src/lib/repos/types.ts` unless reconnaissance proves `description` is not type-allowed (Oracle indicates Omit/Partial already permits it)
- ❌ Display description on the category list/index page
- ❌ Display description in category picker dropdowns or expense forms
- ❌ Add character counter UI
- ❌ Add `maxlength`, character limits, or JS validation logic / error messages (no length cap requested)
- ❌ Add markdown rendering or rich-text editor
- ❌ Create new Svelte components (inline changes only)
- ❌ Change color or icon UI sections
- ❌ Run `npm run format` and commit Prettier whitespace churn in untouched sections — stage only intentional diffs
- ❌ Add formal unit/integration tests (Playwright QA only)
- ❌ Re-seed the database, wipe transactions, or run `quid-api clear-transactions`
- ❌ Modify AI prompt template or `_format_categories` behavior

### Spec Framework Integration
_No SDD framework detected (no `openspec/` or `.specify/` directories in this repo). Section omitted._

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — all verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (`webui/playwright.config*`, `npm run test:e2e`)
- **Automated tests**: NONE (user choice) — agent-executed QA scenarios only
- **Framework**: Playwright is available but used in agent-driven exploratory mode, not committed as test suite
- **TDD**: No

### QA Policy
Every task includes agent-executed Playwright/Bash QA scenarios. Evidence is saved to `.omo/evidence/task-{N}-{slug}.{ext}`.

- **Add/Edit form UI**: Playwright (navigate, fill, intercept POST/PATCH, assert payload + DOM)
- **Mock repo behavior**: Playwright in mock-mode OR Node REPL via Bash (`bun -e` / `node -e`) importing the module
- **Build/type-check**: Bash (`npm run check`, `npm run build`)
- **Scope guard**: Bash (`git diff --stat`, `git diff` on forbidden paths)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Reconnaissance — sequential gate before edits):
└── Task 1: Read + map form patterns, repo internals, types.ts contract [quick]

Wave 2 (After Wave 1 — two parallel tasks; each owns a distinct file):
├── Task 2: Add description input to ADD form AND EDIT form (single file: +page.svelte) [visual-engineering]
└── Task 3: Fix mockCategoryRepository (seed + create + update) [quick]

Wave 3 (After Wave 2 — verification):
└── Task 4: Run npm check + build + Playwright QA suite + scope diff [unspecified-high]

Wave FINAL (After Task 4 — 4 parallel reviewers, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high + playwright skill)
└── Task F4: Scope fidelity check (deep)
-> Present consolidated results -> Wait for explicit user okay

Critical Path: 1 → 2 → 4 → F1-F4 → user okay
Max Concurrent: 2 (Wave 2 — limited by file ownership: Task 2 owns +page.svelte, Task 3 owns mockCategoryRepository.ts)
Parallel Speedup: small task; recon gate and 2-task wave dominate
```

> **Note on wave size**: Wave 2 has only 2 tasks because the implementation surface is two files. Combining Add+Edit form work into one task is required (same file), and the mock repo is the only other independent unit. This is dependency-justified per the Maximum Parallelism Principle.

### Dependency Matrix

- **1**: blocked by none; blocks 2, 3
- **2**: blocked by 1; blocks 4
- **3**: blocked by 1; blocks 4
- **4**: blocked by 2, 3; blocks F1-F4
- **F1-F4**: blocked by 4; blocks user okay

### Agent Dispatch Summary

- **Wave 1**: 1 — Task 1 → `quick`
- **Wave 2**: 2 — Task 2 → `visual-engineering`, Task 3 → `quick`
- **Wave 3**: 1 — Task 4 → `unspecified-high`
- **FINAL**: 4 — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high` (+ playwright skill), F4 → `deep`

---

## TODOs

- [x] 1. Reconnaissance: read form patterns, mock repo, and types contract

  **Completed**: Findings in `.omo/evidence/task-1-recon.md`

  Key findings:
  - Form uses Svelte 5 `$state` runes; individual `let` variables (not a form object)
  - Add form state: `let newName`, `let newColor`, `let newIcon`, `let newError`, `let submittingNew`
  - Edit form state: `let editingId`, `let editName`, `let editColor`, `let editIcon`, `let editError`, `let savingEdit`
  - Edit data source: `startEdit(cat)` function sets individual vars; `cancelEdit()` resets them
  - Input/textarea: raw HTML, no wrapper component; Tailwind classes on Add form: `w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none`; Edit form labels use `text-xs` (vs `text-sm` in Add)
  - Add reset: `newName = ''; newColor = pickRandomDefaultColor(); newIcon = FALLBACK_CATEGORY_ICON`
  - Mock create: `s.categories.push({ id, name, color, icon })` — description missing
  - Mock update: per-field `if (patch.X !== undefined)` guard pattern — needs description guard
  - types.ts verdict: YES, description already type-allowed via `Omit<Category, 'id'>` / `Partial<Omit<Category, 'id'>>`
  - Mock store seed: imported from `seed.ts` via `defaultCategories()` — seed already has descriptions
  - Edit form description textarea placement: AFTER `</div>` closing the `sm:flex-row sm:items-start` inner div (line 479), BEFORE `{#if editError}` (line 480)
  - Add form description textarea placement: AFTER `</div>` closing the `sm:flex-row` inner div (line 295), BEFORE `{#if newError}` (line 297)

- [x] 2. Add description textarea to BOTH the Add and Edit category forms

  **What to do**:
  - In `webui/src/routes/categories/+page.svelte`, make all changes in a single coherent edit:

  *Script section — state declarations* (after existing `$state` vars):
  - After line 26 (`let newError = $state('');`): add `let newDescription = $state('');`
  - After line 33 (`let editError = $state('');`): add `let editDescription = $state('');`

  *Script section — startEdit function* (line 109-116):
  - After `editIcon = normalizeCategoryIcon(cat.icon);` add: `editDescription = cat.description ?? '';`

  *Script section — cancelEdit function* (line 118-125):
  - After `editIcon = FALLBACK_CATEGORY_ICON;` add: `editDescription = '';`

  *Script section — handleAdd handler* (line 98):
  - Change: `await addCategory({ name: newName.trim(), color: newColor, icon: newIcon });`
  - To: `await addCategory({ name: newName.trim(), color: newColor, icon: newIcon, description: newDescription.replace(/\s+/g, ' ').trim() });`
  - After line 101 (`newIcon = FALLBACK_CATEGORY_ICON;`): add `newDescription = '';`

  *Script section — saveEdit handler* (lines 151-154):
  - Add `description` to the patch object:
    ```
    const patch: Partial<Omit<Category, 'id'>> = {
        color: editColor,
        icon: editIcon,
        description: editDescription.replace(/\s+/g, ' ').trim()
    };
    ```

  *Add form markup* — insert a full-width description block AFTER line 295 (`</div>` closing the `sm:flex-row` div) and BEFORE line 297 (`{#if newError}`):
  ```svelte
  		<div class="flex flex-col gap-1">
  			<label
  				for="new-category-description"
  				class="text-sm font-medium text-ctp-subtext0"
  			>
  				Description
  			</label>
  			<textarea
  				id="new-category-description"
  				data-testid="new-category-description"
  				name="description"
  				rows="3"
  				placeholder="e.g. Daily food shopping. Excludes restaurants."
  				bind:value={newDescription}
  				class="w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none resize-none"
  			></textarea>
  			<p class="text-xs text-ctp-subtext0">Used by AI when categorising transactions. Describe what belongs here and what doesn't.</p>
  		</div>
  ```

  *Edit form markup* — insert a full-width description block AFTER line 479 (`</div>` closing the inner `sm:flex-row sm:items-start` div) and BEFORE line 480 (`{#if editError}`):
  ```svelte
  					<div class="flex flex-col gap-1">
  						<label
  							for={`edit-description-${category.id}`}
  							class="text-xs font-medium text-ctp-subtext0"
  						>
  							Description
  						</label>
  						<textarea
  							id={`edit-description-${category.id}`}
  							data-testid="category-edit-description"
  							name="description"
  							rows="3"
  							placeholder="e.g. Daily food shopping. Excludes restaurants."
  							bind:value={editDescription}
  							class="w-full rounded-md border border-ctp-surface2 bg-ctp-base px-3 py-2 text-sm text-ctp-text placeholder:text-ctp-overlay0 focus:border-ctp-accent focus:outline-none resize-none"
  						></textarea>
  						<p class="text-xs text-ctp-subtext0">Used by AI when categorising transactions. Describe what belongs here and what doesn't.</p>
  					</div>
  ```

  **Must NOT do**:
  - Touch the mock repo (Task 3 owns it)
  - Modify color or icon UI sections
  - Add `maxlength`, character counters, validation messages, or new components
  - Modify `domain.ts`, `seed.ts`, `httpCategoryRepository.ts`, or `types.ts`
  - Run `npm run format` outside the changed lines (no Prettier churn in untouched markup)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 3 — different file)
  - **Parallel Group**: Wave 2 (with Task 3)
  - **Blocks**: Task 4
  - **Blocked By**: Task 1

  **Acceptance Criteria**:
  - [ ] Add form markup includes a `<textarea>` with `name="description"`, `rows="3"`, placed as a full-width row AFTER the icon/name/color/button row and BEFORE the error block
  - [ ] Edit form markup includes the same `<textarea>` in the same relative position
  - [ ] Label text is "Description"; helper text is present in both forms
  - [ ] Add handler sends `description` key in the POST body — always (trim + newline collapse)
  - [ ] Edit handler sends `description` key in the PATCH body — always (trim + newline collapse)
  - [ ] Edit textarea pre-fills with current description, falling back to `""` if undefined
  - [ ] Successful add resets the description field along with the others
  - [ ] `npm run check` exits 0 after edit
  - [ ] `git diff --stat` shows ONLY `webui/src/routes/categories/+page.svelte` modified

  **Commit**: NO (folds into Wave 2+3 squash commit)

- [x] 3. Fix mockCategoryRepository to persist description

  **What to do**:
  - In `webui/src/lib/repos/mockCategoryRepository.ts`:
    - In `create`: change `s.categories.push({ id, name, color, icon })` → `s.categories.push({ id, name, color, icon, description: input.description ?? '' })`
    - In `update`: after the `if (patch.icon !== undefined)` block, add:
      ```ts
      if (patch.description !== undefined) {
          s.categories[idx].description = patch.description;
      }
      ```
  - The seed is imported from `seed.ts` via `defaultCategories()` which already includes descriptions — no seed changes needed.
  - Maintain the existing return shape; do not change function signatures.

  **Must NOT do**:
  - Modify `webui/src/lib/repos/seed.ts`
  - Modify `webui/src/lib/repos/httpCategoryRepository.ts`
  - Modify `webui/src/lib/repos/types.ts`
  - Modify `domain.ts`
  - Change function signatures or exports
  - Run `npm run format` and commit Prettier churn

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none required

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2 — different file)
  - **Parallel Group**: Wave 2 (with Task 2)
  - **Blocks**: Task 4
  - **Blocked By**: Task 1

  **Acceptance Criteria**:
  - [ ] Every category in the mock seed has a `description` field (string, may be `""`) — they come from `seed.ts` which already has descriptions
  - [ ] `create({ name, color, icon, description: "test" })` returns an object whose `description === "test"`
  - [ ] Subsequent `getAll()` / `get(id)` returns the same description
  - [ ] `update(id, { description: "patched" })` returns / persists `description === "patched"`
  - [ ] `update(id, {})` (empty patch) does NOT clobber existing description
  - [ ] `npm run check` exits 0
  - [ ] `git diff --stat` shows ONLY `webui/src/lib/repos/mockCategoryRepository.ts` modified

  **Commit**: NO (folds into Wave 2+3 squash commit)

- [x] 4. Verification suite: build, type-check, scope diff, end-to-end QA

  **What to do**:
  - Run `cd webui && npm run check` — capture full output, confirm exit 0
  - Run `cd webui && npm run build` — capture full output, confirm exit 0
  - Run `git diff --name-only` from repo root — confirm only allowed files
  - Confirm the AI prompt still includes description by running: `cd api && uv run python -c "from quid_api.ai_categorization import _format_categories; print(_format_categories([('Foo', 'Test description')]))"` — expect output line containing `- Foo: Test description`

  **Commit**: YES (single squash after this task is green)
  - Message: `feat(webui): expose category description in Add/Edit forms`
  - Files: `webui/src/routes/categories/+page.svelte`, `webui/src/lib/repos/mockCategoryRepository.ts`
  - Pre-commit: `cd webui && npm run check && npm run build` (already passed above)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed.** Never mark F1-F4 as checked before getting user's okay. Rejection or feedback → fix → re-run → present again → wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`

  **Output**: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`

  **Output**: `Build [PASS/FAIL] | Check [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)

  **Output**: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`

  **Output**: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 2+3 squash (default)**:
  - Message: `feat(webui): expose category description in Add/Edit forms`
  - Files: `webui/src/routes/categories/+page.svelte`, `webui/src/lib/repos/mockCategoryRepository.ts`
  - Pre-commit: `cd webui && npm run check && npm run build` (must exit 0)

---

## Success Criteria

### Verification Commands

```bash
# Type-check & build (from webui/)
npm run check        # Expected: exit 0
npm run build        # Expected: exit 0

# Scope guard (from repo root)
git diff --name-only # Expected: only +page.svelte, mockCategoryRepository.ts

# AI prompt smoke test — confirm description still flowing to AI builder (from api/)
uv run python -c "from quid_api.ai_categorization import _format_categories; print(_format_categories([('Foo', 'Test description')]))"
# Expected output line: "- Foo: Test description"
```

### Final Checklist
- [ ] All "Must Have" items present (verified by F1)
- [ ] All "Must NOT Have" items absent (verified by F1 + F4)
- [ ] `npm run check` and `npm run build` clean
- [ ] Playwright QA scenarios pass with evidence captured
- [ ] User has given explicit "okay" after reviewing F1-F4 consolidated results
