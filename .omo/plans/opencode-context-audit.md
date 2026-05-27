# OpenCode Global Context Audit & Optimization Recommendations

## TL;DR

> **Quick Summary**: Audit Grant's global OpenCode context sources (config, skills, plugins, MCP tool schemas, builtin context), measure token cost per source via tiktoken, and produce a single markdown report with prioritized removal recommendations.
>
> **Deliverables**:
> - `.omo/reports/opencode-context-audit.md` — the report with per-source token counts, category aggregation, and recommendations
> - `/tmp/count_tokens.py` — reproducible token-counting script referenced from the report
> - `/tmp/opencode-audit/` — working directory for intermediate JSON inventories (one per source category)
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 → Task 8 → Task 10 → Task 11 → Task 12 → Task 13 → F1-F4

---

## Context

### Original Request
"I want to analyse what goes into context when I work in OpenCode. I think I have too many things installed, I want to optimise."

### Interview Summary
**Key Decisions**:
- Symptom: System prompt feels too large at session start
- Scope: **Global only** (no project-specific files)
- Deliverable: **Report-only** (no automated cleanup; user decides removals)
- Metric: **Token count per source** via tiktoken (cl100k_base)
- Suspects: Everything is fair game — data drives recommendations

**Research Findings**:
- `~/.config/opencode/`: opencode.json (252 lines, registers `pencil` MCP + 3 plugins), oh-my-openagent.json (188 lines, agent routing), tui.json (48 chars)
- No user-level AGENTS.md
- Skills: `~/.claude/skills/homelab` → symlink to `/Users/grant/dev/homelab-skill`; `~/.claude/skills/swiftui-skills` → symlink to `~/.agents/skills/swiftui-skills/`
- Plugins installed (npm): opencode-claude-auth, oh-my-openagent, opencode-openai-codex-auth + many transitives
- Many additional tools visible in session (Ast_grep, Background, Context7, Session_*, Lsp_*, Look_at, Question, Pencil, Webfetch, Websearch, Skill, Task, Bash, Edit, Read, Write, Grep, Glob, Grep_app, Interactive_bash, Todowrite) — source must be discovered
- Skill listing in system prompt includes ~30+ slash commands from plugins (superpowers, document-skills, code-review, frontend-design) — these are major suspects
- `uv` available; tiktoken not installed but `uvx --with tiktoken` works
- OpenCode session DB at `~/.local/share/opencode/opencode.db` (sqlite, 68MB) — schema must be checked before assuming system prompts are stored

### Metis Review
**Critical guardrails (addressed)**:
- Distinguish system-prompt tokens (once per session) from tool-definition tokens (per request) — separate columns in report
- MCP tool schemas are runtime-fetched, not in config files — must run `tools/list` per server OR mark as gap
- No usage-frequency data exists — drop that axis to avoid fabrication
- Resolve symlinks and dedupe by inode
- Don't measure `node_modules/` directory sizes — only injected content counts
- Check session DB schema before assuming it stores assembled prompts
- tiktoken cl100k_base is a ±10-20% approximation of Anthropic's actual tokenizer; report must note this
- Every removal recommendation must cite exact `file:line` or removal command
- "Sources Not Measured" section mandatory with explicit reasons

---

## Work Objectives

### Core Objective
Audit Grant's global OpenCode context sources and produce a markdown report with tiktoken-based token counts, separated by system-prompt vs tool-definition category, plus prioritized removal recommendations.

### Concrete Deliverables
- `.omo/reports/opencode-context-audit.md` — single audit report
- `/tmp/count_tokens.py` — reproducible counter script
- `/tmp/opencode-audit/inventory-*.json` — intermediate inventories per category

### Definition of Done
- [ ] Report file exists at `.omo/reports/opencode-context-audit.md`
- [ ] Running `uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json` reproduces every system-prompt token count in the report
- [ ] Running `uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/flat-tool-def.json` reproduces every tool-definition token count in the report
- [ ] Every source listed has either a numeric token count OR a "Sources Not Measured" entry explaining why
- [ ] Every recommendation has a removal path (`file:line` or shell command)
- [ ] System-prompt-category and tool-definition-category subtotals appear separately
- [ ] tiktoken approximation caveat is stated in the report

### Must Have
- Two separate token columns: system-prompt-once vs tool-definition-per-request
- A "Sources Not Measured" section listing what could not be statically measured + why
- Reproducible counter script saved at `/tmp/count_tokens.py` and referenced in the report
- For every recommendation: exact removal path (file path + line OR specific command)
- Symlink resolution and inode-dedup for skills
- An "Approximation caveat" paragraph noting cl100k_base is a GPT-4 tokenizer, not Anthropic's

### Must NOT Have (Guardrails)
- NO modification of any config file (this is report-only)
- NO touching project files (`/Users/grant/dev/quid/.opencode/`, `/Users/grant/dev/quid/AGENTS.md`, or any other project-level path)
- NO fabricated usage-frequency data (frequency is unknowable from static analysis)
- NO double-counting symlinked skills (homelab, swiftui-skills)
- NO reporting `node_modules/` raw directory sizes as "context cost"
- NO recommendations without a removal path
- NO running `opencode` to create a fresh session (could trigger billing/side effects)
- NO writing scripts to permanent locations like `~/.config/opencode/`
- NO estimated/inferred numbers — every count must come from script output on actual content
- NO assumption that the session DB stores system prompts without verifying schema first

### Spec Framework Integration
Not applicable — no SDD framework (OpenSpec, Spec Kit, BMAD) detected in `/Users/grant/dev/quid/`.

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — All verification is agent-executed.

### Test Decision
- **Infrastructure exists**: N/A — deliverable is a markdown report, not shipped code
- **Automated tests**: NONE
- **Framework**: N/A
- **Verification approach**: Agent-executed QA scenarios — reproducibility of script output, presence of every source category in report, removal-path validation for every recommendation

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Counter script**: Bash invocation with explicit inventory (`uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json`), compare numeric output across two runs (must match exactly)
- **Inventories**: Bash + jq — assert presence of expected keys, count of entries
- **Report**: Bash + grep — assert presence of required section headers, presence of numeric counts, presence of removal paths

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — runs in parallel):
├── 1. Counter script + working dir setup [quick]
├── 2. Inventory: opencode config files [quick]
├── 3. Inventory: skills (symlink-resolved, inode-deduped) [quick]
├── 4. Inventory: agent prompts from oh-my-openagent + plugin packages [unspecified-high]
├── 5. Inventory: command files / slash-command descriptions [unspecified-high]
├── 6. Inventory: MCP tool schemas via tools/list (or mark gap) [unspecified-high]
└── 7. Inspect OpenCode session DB schema + check CLI debug flags [unspecified-high]

Wave 2 (Measurement — after Wave 1):
├── 8. Run counter on system-prompt-category sources (depends: 1, 2, 3, 4, 5, 7) [quick]
├── 9. Run counter on tool-definition-category sources (depends: 1, 6) [quick]
└── 10. Aggregate + cross-reference with assembled prompt if available (depends: 7, 8, 9) [unspecified-high]

Wave 3 (Synthesis — after Wave 2):
├── 11. Draft report skeleton: TL;DR, methodology, caveats, Sources Not Measured (depends: 10) [writing]
├── 12. Fill per-source tables + category totals (depends: 11) [writing]
└── 13. Write prioritized removal recommendations with removal paths (depends: 12) [writing]

Wave FINAL (Parallel reviews — then user okay):
├── F1. Plan compliance audit (oracle)
├── F2. Code/script quality review (unspecified-high)
├── F3. Manual QA of report content (unspecified-high)
└── F4. Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: 1 → 8 → 10 → 11 → 12 → 13 → F1-F4
Max Concurrent: 7 (Wave 1)
```

### Dependency Matrix

- **1**: blocked-by none → blocks 8, 9, 10
- **2**: blocked-by none → blocks 8
- **3**: blocked-by none → blocks 8
- **4**: blocked-by none → blocks 8
- **5**: blocked-by none → blocks 8
- **6**: blocked-by none → blocks 9
- **7**: blocked-by none → blocks 8, 10
- **8**: blocked-by 1, 2, 3, 4, 5, 7 → blocks 10
- **9**: blocked-by 1, 6 → blocks 10
- **10**: blocked-by 7, 8, 9 → blocks 11
- **11**: blocked-by 10 → blocks 12
- **12**: blocked-by 11 → blocks 13
- **13**: blocked-by 12 → blocks F1-F4

### Agent Dispatch Summary

- **Wave 1** (7 tasks): T1→quick, T2→quick, T3→quick, T4→unspecified-high, T5→unspecified-high, T6→unspecified-high, T7→unspecified-high
- **Wave 2** (3 tasks): T8→quick, T9→quick, T10→unspecified-high
- **Wave 3** (3 tasks): T11→writing, T12→writing, T13→writing
- **FINAL** (4 tasks): F1→oracle, F2→unspecified-high, F3→unspecified-high, F4→deep

---

## TODOs

- [x] 1. Create token-counter script and working directory

  **What to do**:
  - Create `/tmp/opencode-audit/` directory for intermediate JSON inventories
  - Write `/tmp/count_tokens.py` using `tiktoken.get_encoding("cl100k_base")`:
    - Accept a list of `(label, path)` pairs OR a directory glob
    - Read file contents as UTF-8 (errors='replace')
    - Return list of `{label, path, bytes, tokens}` entries
    - Resolve symlinks via `os.path.realpath`, dedupe by `os.stat().st_ino`
    - When given a JSON inventory file, also accept inline strings (not just file paths) for content that isn't on disk (e.g., MCP tool descriptions fetched live)
    - Output a stable JSON to stdout sorted by `tokens DESC` for reproducibility
  - Verify the invocation works: `uv tool run --with tiktoken python /tmp/count_tokens.py --help`

  **Must NOT do**:
  - Save script anywhere under `~/.config/opencode/` (would alter global config dir)
  - Hard-code any token counts
  - Use `print()` for debug noise — only emit the final JSON
  - Read project files

  **Recommended Agent Profile**:
  - **Category**: `quick` — single Python file, ~50 lines, straightforward
  - **Skills**: none — standard library + tiktoken is sufficient

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: None — start immediately

  **References**:
  - tiktoken docs: `https://github.com/openai/tiktoken#how-to-count-tokens-with-tiktoken` — basic encode/decode API
  - cl100k_base usage: `enc = tiktoken.get_encoding("cl100k_base"); tokens = len(enc.encode(text))`
  - `uv tool run --with tiktoken python script.py` — runs script with tiktoken pulled in ephemerally
  - Symlink resolution: `os.path.realpath(path)` + `os.stat(path).st_ino` for dedup

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/count_tokens.py`
  - [ ] Directory exists: `/tmp/opencode-audit/`
  - [ ] Invocation succeeds: `uv tool run --with tiktoken python /tmp/count_tokens.py --help` → exit 0
  - [ ] Smoke test passes: `echo '[{"label":"x","content":"hello world"}]' | uv tool run --with tiktoken python /tmp/count_tokens.py --inline` → returns JSON with `tokens: 2`

  **QA Scenarios**:

  ```
  Scenario: Happy path — script encodes a known string
    Tool: Bash
    Preconditions: /tmp/count_tokens.py exists; uv available
    Steps:
      1. echo '[{"label":"test","content":"The quick brown fox"}]' > /tmp/opencode-audit/smoke.json
      2. uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/smoke.json > /tmp/opencode-audit/smoke.out
      3. cat /tmp/opencode-audit/smoke.out
    Expected Result: Valid JSON with one entry, "tokens" field is a positive integer (typically 4 for that phrase under cl100k_base)
    Failure Indicators: Invalid JSON, missing fields, tokens=0, ImportError
    Evidence: .omo/evidence/task-1-smoke.json

  Scenario: Symlink dedup — same file under two paths counted once
    Tool: Bash
    Preconditions: ln -s ~/.claude/skills/swiftui-skills/manifest.json /tmp/opencode-audit/link.json
    Steps:
      1. Build inventory referencing BOTH the real path and the symlink
      2. Run counter
      3. Assert the inode dedup logic kept only one entry
    Expected Result: Output JSON contains only one entry (the realpath); duplicate symlink not double-counted
    Evidence: .omo/evidence/task-1-symlink-dedup.json
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-1-smoke.json` — smoke test output
  - [ ] `.omo/evidence/task-1-symlink-dedup.json` — symlink dedup result

  **Commit**: NO (groups with all tasks at the end)

- [x] 2. Inventory opencode config files

  **What to do**:
  - Enumerate global config files actually loaded by OpenCode:
    - `~/.config/opencode/opencode.json`
    - `~/.config/opencode/oh-my-openagent.json`
    - `~/.config/opencode/tui.json`
  - Read each, capture: path, byte size, content
  - Skip `*.backup-*` and `*.bak-*` files (not loaded by OpenCode)
  - Skip `node_modules/` directory contents (per Metis: only injected content counts, not package code)
  - Skip `package.json` / `package-lock.json` (build artifacts, not context)
  - Skip `.gitignore` (not loaded as runtime context)
  - Output JSON inventory: `/tmp/opencode-audit/inventory-config.json` with entries `[{label, path, content}, ...]`

  **Must NOT do**:
  - Include backup files (Metis: would count duplicates)
  - Include node_modules content as a context source (Metis: package code ≠ context injection)
  - Reference any path under `/Users/grant/dev/quid/`

  **Recommended Agent Profile**:
  - **Category**: `quick` — file enumeration + JSON output
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 8
  - **Blocked By**: None

  **References**:
  - `~/.config/opencode/opencode.json` — registers `pencil` MCP, lists 3 npm plugins, defines provider configs (line 1-252)
  - `~/.config/opencode/oh-my-openagent.json` — defines agent model routing for sisyphus/hephaestus/oracle/librarian/explore/metis/momus etc. (line 1-188)
  - Filename filter pattern: skip `*.backup-*`, `*.bak-*`, `package*.json`, `*.gitignore`, dirs `node_modules/`

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/inventory-config.json`
  - [ ] JSON is valid (`jq '.' /tmp/opencode-audit/inventory-config.json` returns without error)
  - [ ] Contains entries for opencode.json, oh-my-openagent.json, tui.json — at minimum 3 entries
  - [ ] Contains NO entries with `backup` or `bak` in the path
  - [ ] Contains NO entries under `node_modules/`

  **QA Scenarios**:

  ```
  Scenario: Happy path — inventory enumerates expected files
    Tool: Bash
    Preconditions: ~/.config/opencode/ contains the known files from recon
    Steps:
      1. jq 'length' /tmp/opencode-audit/inventory-config.json
      2. jq -r '.[].path' /tmp/opencode-audit/inventory-config.json | sort
    Expected Result: Count ≥ 3; paths include opencode.json, oh-my-openagent.json, tui.json
    Evidence: .omo/evidence/task-2-paths.txt

  Scenario: Negative — backup files are excluded
    Tool: Bash
    Steps:
      1. jq -r '.[].path' /tmp/opencode-audit/inventory-config.json | grep -E 'backup|\.bak' || echo "OK no backups"
    Expected Result: "OK no backups" — no backup files in inventory
    Evidence: .omo/evidence/task-2-no-backups.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-2-paths.txt`
  - [ ] `.omo/evidence/task-2-no-backups.txt`

  **Commit**: NO (groups at end)

- [x] 3. Inventory skills (symlink-resolved, inode-deduped)

  **What to do**:
  - Walk `~/.claude/skills/` and `~/.agents/skills/` (both directories)
  - For each entry: resolve symlink via `realpath`, capture inode via `stat`
  - Read `SKILL.md` (or `manifest.json` if SKILL.md absent) for each unique inode
  - Build inventory entries: `{label, original_path, resolved_path, inode, content}`
  - Dedupe entries by inode — same underlying file counted once
  - Note discovered symlinks in inventory metadata (e.g., `{"symlinks": [{"link":"~/.claude/skills/homelab", "target":"/Users/grant/dev/homelab-skill"}]}`)
  - Output: `/tmp/opencode-audit/inventory-skills.json`

  **Must NOT do**:
  - Count the same skill twice (homelab is symlinked from `~/.claude/skills/`, swiftui-skills is symlinked into `~/.claude/skills/` from `~/.agents/skills/`)
  - Include `.DS_Store` files
  - Recurse into skill's full repo content (e.g., `/Users/grant/dev/homelab-skill/` may contain large data dirs — only the SKILL.md / manifest matters for context contribution)
  - Reference quid project paths

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires careful symlink handling and inode dedup
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 8
  - **Blocked By**: None

  **References**:
  - Recon found 2 skills: `homelab` (→ /Users/grant/dev/homelab-skill, has SKILL.md per system listing), `swiftui-skills` (→ ~/.agents/skills/swiftui-skills/, has manifest.json + setup.sh, has docs/ examples/ prompts/ metadata/ subdirs)
  - Inode dedup pattern: `os.stat(path).st_ino` collected in a `set()`; skip if seen
  - `~/.claude/skills/homelab/SKILL.md` exists (per built-in skills listing this turn); read that file specifically for the SKILL definition
  - `~/.agents/skills/swiftui-skills/manifest.json` (429 bytes per recon) likely the canonical description

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/inventory-skills.json`
  - [ ] JSON contains exactly 2 unique skill entries (homelab, swiftui-skills) — NO duplicates by inode
  - [ ] Each entry has: `label`, `original_path`, `resolved_path`, `inode`, `content`
  - [ ] Symlinks metadata captures both `homelab → /Users/grant/dev/homelab-skill` and `swiftui-skills → ~/.agents/skills/swiftui-skills`

  **QA Scenarios**:

  ```
  Scenario: Happy path — two skills enumerated, deduped
    Tool: Bash
    Steps:
      1. jq '[.entries[].inode] | unique | length' /tmp/opencode-audit/inventory-skills.json
      2. jq '.entries | length' /tmp/opencode-audit/inventory-skills.json
    Expected Result: Both queries return 2 (matching: each skill represented once; inode unique)
    Evidence: .omo/evidence/task-3-skill-count.txt

  Scenario: Negative — running with a duplicate path doesn't double-count
    Tool: Bash
    Steps:
      1. Manually inject a duplicate path entry into a test inventory
      2. Re-run dedup logic
      3. Confirm output count unchanged
    Expected Result: Dedup keeps only the first occurrence
    Evidence: .omo/evidence/task-3-dedup.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-3-skill-count.txt`
  - [ ] `.omo/evidence/task-3-dedup.txt`

  **Commit**: NO (groups at end)

- [ ] 4. Inventory agent prompts + plugin-injected content

  **What to do**:
  - From `~/.config/opencode/oh-my-openagent.json`, extract any agent system-prompt fields (Metis flagged: 188-line config may expand significantly when agent prompts are loaded). Inspect schema and identify which keys hold prompt text (e.g., `agents.*.prompt`, `agents.*.system`, or referenced markdown paths).
  - Walk `~/.config/opencode/node_modules/` and identify plugin packages that ship descriptions / system prompts / skill definitions. For each top-level `@opencode-ai/*`, `oh-my-openagent`, `opencode-*` package:
    - Look for `package.json` keys hinting at context injection (e.g., `opencode`, `contributes`, `prompts`)
    - Look for bundled markdown files (`*.md`), JSON manifests with description fields, or skill files
  - DO NOT count raw `*.js` / `*.ts` source as context — only the strings the plugin actually injects (prompts, descriptions, skill bodies)
  - For each injectable string found, capture: `{label, source_package, key_or_path, content}`
  - Output: `/tmp/opencode-audit/inventory-plugin-injects.json`
  - If a plugin's injected content cannot be statically determined (e.g., it builds strings programmatically), add a `gap` entry: `{label, source_package, reason}`

  **Must NOT do**:
  - Report the size of `*.js` files as context cost (per Metis: package code ≠ context)
  - Recurse into `node_modules/.../node_modules/` (transitive deps don't inject context directly)
  - Invent injection paths — if unsure, mark as `gap` with reason

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires schema introspection of multiple plugins, careful gap-marking
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 8
  - **Blocked By**: None

  **References**:
  - `~/.config/opencode/oh-my-openagent.json` (188 lines) — recon shows `agents.sisyphus.model`, `agents.oracle.fallback_models` etc. Need to read full file to find any prompt fields.
  - Plugin packages found in `~/.config/opencode/node_modules/`: `@opencode-ai/*` (multiple), `oh-my-openagent`, plus transitives like `effect`, `zod`, etc. Only the opencode-related packages inject context.
  - Slash commands visible in this session's listing (e.g., `/superpowers:using-git-worktrees`, `/document-skills:theme-factory`, `/code-review:code-review`, `/frontend-design:frontend-design`) come from plugins — their descriptions are part of context.
  - Pattern: `find ~/.config/opencode/node_modules/@opencode-ai -name "*.md" -o -name "manifest.json" | head -50` to find candidate injection sources

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/inventory-plugin-injects.json`
  - [ ] JSON contains `entries` array AND `gaps` array
  - [ ] At least one entry per opencode-related plugin (or a gap entry explaining why)
  - [ ] No entries reference `.js`/`.ts` source files as context

  **QA Scenarios**:

  ```
  Scenario: Happy path — plugin manifests enumerated
    Tool: Bash
    Steps:
      1. jq '.entries | length' /tmp/opencode-audit/inventory-plugin-injects.json
      2. jq -r '.entries[].source_package' /tmp/opencode-audit/inventory-plugin-injects.json | sort -u
      3. jq '.gaps | length' /tmp/opencode-audit/inventory-plugin-injects.json
    Expected Result: At least 3 source_packages enumerated (oh-my-openagent + opencode-claude-auth + opencode-openai-codex-auth); gaps array exists (may be empty if all measurable)
    Evidence: .omo/evidence/task-4-plugin-list.txt

  Scenario: Negative — no .js source files counted
    Tool: Bash
    Steps:
      1. jq -r '.entries[].key_or_path' /tmp/opencode-audit/inventory-plugin-injects.json | grep -E '\.(js|ts)$' || echo "OK no source files"
    Expected Result: "OK no source files"
    Evidence: .omo/evidence/task-4-no-source.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-4-plugin-list.txt`
  - [ ] `.omo/evidence/task-4-no-source.txt`

  **Commit**: NO (groups at end)

- [ ] 5. Inventory slash-command descriptions visible in session

  **What to do**:
  - The system prompt for this very session listed ~30+ slash commands across plugins (e.g., `/superpowers:using-git-worktrees`, `/document-skills:*`, `/code-review:*`, `/frontend-design:*`, `/swiftui-skills`, `/homelab`, `/playwright`, `/git-master`, `/review-work`, etc.). These descriptions are major context contributors.
  - Discover the source of each command:
    - Check `~/.config/opencode/node_modules/<plugin>/` for command-definition files (markdown, YAML, or JSON)
    - For each plugin, list its commands and capture each command's `description` field + name
  - Output `/tmp/opencode-audit/inventory-commands.json` with entries `{command, plugin, source_path, name, description}`
  - For commands whose source can't be located, add to `gaps` with reason "source not found in plugin tree"

  **Must NOT do**:
  - Re-type command descriptions from the system prompt as if they were ground truth — must trace each to a source file (or mark as gap)
  - Include commands that don't appear in the actual session listing
  - Pull project-level commands (e.g., `/start-work`, `/handoff` may be built-in; verify before classifying)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires tracing each command back to its plugin source
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 8
  - **Blocked By**: None

  **References**:
  - Slash commands observed in this session's listing (read the system-prompt header of any recent session for the canonical list)
  - Plugin command convention varies: some plugins use `commands/*.md`, some use `package.json` `opencode.commands`, some are programmatically registered
  - Pattern to discover: `find ~/.config/opencode/node_modules -path '*/commands/*' -o -path '*/skills/*' 2>/dev/null | head -100`
  - Built-in vs plugin: commands prefixed `/document-skills:`, `/superpowers:`, `/code-review:`, `/frontend-design:` come from plugins by that name; unprefixed like `/init-deep`, `/ralph-loop`, `/cancel-ralph`, `/refactor`, `/start-work`, `/stop-continuation`, `/remove-ai-slops`, `/handoff`, `/hyperplan` likely built-in (in opencode binary itself)

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/inventory-commands.json`
  - [ ] At least 20 command entries (system prompt listing has ~30+)
  - [ ] Each entry has source traced (either `source_path` or `gap` with reason)
  - [ ] No project-scope command entries

  **QA Scenarios**:

  ```
  Scenario: Happy path — commands enumerated with source traced
    Tool: Bash
    Steps:
      1. jq '.entries | length' /tmp/opencode-audit/inventory-commands.json
      2. jq -r '.entries[] | "\(.command)\t\(.source_path // "GAP")"' /tmp/opencode-audit/inventory-commands.json | head -20
    Expected Result: ≥20 entries; majority have a real source_path; gaps clearly marked
    Evidence: .omo/evidence/task-5-commands.txt

  Scenario: Negative — built-in commands flagged as not-from-plugin-tree
    Tool: Bash
    Steps:
      1. jq -r '.gaps[] | "\(.command): \(.reason)"' /tmp/opencode-audit/inventory-commands.json
    Expected Result: Built-in commands appear in gaps with reason "built into opencode binary" or similar
    Evidence: .omo/evidence/task-5-builtins.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-5-commands.txt`
  - [ ] `.omo/evidence/task-5-builtins.txt`

  **Commit**: NO (groups at end)

- [ ] 6. Inventory MCP tool schemas (live tools/list per server)

  **What to do**:
  - From `~/.config/opencode/opencode.json` extract every entry under the `mcp` key. Recon confirms `pencil` is registered there.
  - Plus: visible session tools include Ast_grep_*, Background_*, Context7_*, Lsp_*, Look_at, Pencil_*, Question, Session_*, Skill_mcp, Webfetch, Websearch_web_search_exa, Grep_app_searchGitHub, Interactive_bash. These come from MCP servers bundled into plugins. Discover each:
    - Search `~/.config/opencode/node_modules/` for `package.json` files with an `mcp` field or scripts named `mcp-server-*`
    - For each discovered MCP server, capture its launch command
  - For each server (registered + discovered): launch it briefly and request its tool list via MCP `tools/list` protocol, capture the JSON schemas. Example invocation pattern:
    - For stdio MCPs: spawn the process, send `{"jsonrpc":"2.0","id":1,"method":"tools/list"}`, read response, kill process
  - If a server cannot be launched (binary missing, requires app context like Pencil.app), mark as `gap` with `{server, reason}`
  - Output: `/tmp/opencode-audit/inventory-mcp-tools.json` with shape `{servers: [{name, launch_cmd, tools: [{name, description, inputSchema}]}], gaps: [...]}`
  - tool description + inputSchema combined are what counts as tool-definition tokens

  **Must NOT do**:
  - Estimate or hand-count tools — every tool schema must be live-fetched (Metis: "Pencil alone likely has 15+ tools" is exactly the kind of hallucination to avoid)
  - Run `opencode` itself to generate a session (could trigger billing/side effects)
  - Modify any config to "test" MCP behavior
  - Reference quid project paths

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires understanding MCP protocol + launching servers safely
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 9
  - **Blocked By**: None

  **References**:
  - `~/.config/opencode/opencode.json` lines 4-14 show pencil MCP config: `command: ["/Applications/Pencil.app/Contents/Resources/app.asar.unpacked/out/mcp-server-darwin-arm64", "--app", "desktop"]`. Pencil requires the .app to be running — may need to be marked as `gap` if not feasible to test.
  - MCP `tools/list` protocol: send `{"jsonrpc":"2.0","method":"tools/list","id":1}` over stdin, read `{"result":{"tools":[...]}}` from stdout
  - Discovery pattern: `find ~/.config/opencode/node_modules -name 'package.json' -exec grep -l '"mcp"' {} \;` to find MCP-enabled packages

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/inventory-mcp-tools.json`
  - [ ] Each registered MCP server appears either with real tool schemas OR in `gaps` with a clear reason
  - [ ] Every tool entry has `name`, `description`, `inputSchema` populated
  - [ ] Total tool count is consistent with the count visible in this session's tool list (sanity check)

  **QA Scenarios**:

  ```
  Scenario: Happy path — at least one MCP server's tools fetched live
    Tool: Bash
    Steps:
      1. jq '.servers | length' /tmp/opencode-audit/inventory-mcp-tools.json
      2. jq -r '.servers[] | "\(.name): \(.tools | length) tools"' /tmp/opencode-audit/inventory-mcp-tools.json
    Expected Result: At least 1 server with tools array length ≥ 1
    Evidence: .omo/evidence/task-6-mcp-counts.txt

  Scenario: Negative — unreachable servers marked as gaps, not faked
    Tool: Bash
    Steps:
      1. jq -r '.gaps[] | "\(.server): \(.reason)"' /tmp/opencode-audit/inventory-mcp-tools.json
    Expected Result: If pencil isn't reachable, it appears here with reason "Pencil.app not running" or similar — NOT silently omitted
    Evidence: .omo/evidence/task-6-mcp-gaps.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-6-mcp-counts.txt`
  - [ ] `.omo/evidence/task-6-mcp-gaps.txt`

  **Commit**: NO (groups at end)

- [ ] 7. Inspect OpenCode session DB schema + check CLI debug flags

  **What to do**:
  - Verify Metis assumption A1: does `~/.local/share/opencode/opencode.db` contain assembled system prompts?
    - Run `sqlite3 ~/.local/share/opencode/opencode.db .tables`
    - Inspect schema of each table (`PRAGMA table_info(<table>);`)
    - Look for columns named `system`, `prompt`, `messages`, `system_prompt`, etc.
    - If found, dump ONE recent row's system-prompt content (just for inspection — do NOT include personal conversation content in the report)
  - Check OpenCode CLI for debug/dump flags: `opencode --help 2>&1`, `opencode debug --help 2>&1`, look for any `--print-prompt`, `--dump-context`, or similar
  - Output: `/tmp/opencode-audit/db-inspection.json` with `{tables: [...], system_prompt_column: bool, sample_prompt_length_chars: int_or_null, cli_dump_flags: [string]}`
  - If a usable dump path exists, the report's "ground truth" cross-check can run; otherwise the report notes the limitation

  **Must NOT do**:
  - Modify the DB
  - Include personal conversation content in any output (this is metadata only)
  - Run `opencode run` or any subcommand that creates a session
  - Reference quid project paths

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires sqlite schema work + careful handling of personal data
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 8, 10
  - **Blocked By**: None

  **References**:
  - `~/.local/share/opencode/opencode.db` (68MB sqlite, recon confirmed)
  - sqlite3 schema commands: `.tables`, `.schema <table>`, `PRAGMA table_info(<table>)`
  - opencode binary path: discover via `which opencode`
  - DON'T dump conversation content — privacy-sensitive

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/db-inspection.json`
  - [ ] `tables` field populated with actual table names from the DB
  - [ ] `system_prompt_column` is a boolean (true if assembled prompts stored, false otherwise)
  - [ ] `cli_dump_flags` array populated (empty if none found)
  - [ ] NO conversation content from the user appears in the file

  **QA Scenarios**:

  ```
  Scenario: Happy path — schema introspected, gap/availability determined
    Tool: Bash
    Steps:
      1. jq '.tables | length' /tmp/opencode-audit/db-inspection.json
      2. jq '.system_prompt_column' /tmp/opencode-audit/db-inspection.json
    Expected Result: Tables list non-empty; system_prompt_column is true OR false (not null)
    Evidence: .omo/evidence/task-7-db-schema.txt

  Scenario: Negative — no personal content in output
    Tool: Bash
    Steps:
      1. grep -iE "grant|homelab|quid|api.key|token=" /tmp/opencode-audit/db-inspection.json || echo "OK clean"
    Expected Result: "OK clean" — only schema metadata, no personal/conversation content
    Evidence: .omo/evidence/task-7-no-pii.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-7-db-schema.txt`
  - [ ] `.omo/evidence/task-7-no-pii.txt`

  **Commit**: NO (groups at end)

- [ ] 8. Run counter on system-prompt-category sources

  **What to do**:
  - Merge inventories from Tasks 2 (config), 3 (skills), 4 (plugin injects), 5 (commands), and any in-DB system prompt sample from Task 7 (if available) into a single `system-prompt` inventory
  - Run `/tmp/count_tokens.py` against this merged inventory
  - Save output to `/tmp/opencode-audit/counts-system-prompt.json` — sorted by `tokens DESC`
  - Each entry: `{label, source_path_or_inline, bytes, tokens, category: "system-prompt"}`

  **Must NOT do**:
  - Include MCP tool schemas here (those are tool-definition category, Task 9)
  - Estimate any count — every number must come from script output
  - Include node_modules raw sizes

  **Recommended Agent Profile**:
  - **Category**: `quick` — JSON merge + script invocation
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 2; depends on Wave 1 outputs)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: 1, 2, 3, 4, 5, 7

  **References**:
  - Counter script: `/tmp/count_tokens.py` (from Task 1)
  - Inventories: `/tmp/opencode-audit/inventory-config.json`, `inventory-skills.json`, `inventory-plugin-injects.json`, `inventory-commands.json`, `db-inspection.json`

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/counts-system-prompt.json`
  - [ ] Entries sorted by `tokens` descending
  - [ ] Sum of `tokens` field appears as a `_total` entry OR computable via `jq '[.[].tokens] | add'`
  - [ ] Re-running the script produces byte-identical output

  **QA Scenarios**:

  ```
  Scenario: Happy path — counts computed and reproducible
    Tool: Bash
    Steps:
      1. uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json > /tmp/run1.json
      2. uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json > /tmp/run2.json
      3. diff /tmp/run1.json /tmp/run2.json
    Expected Result: Empty diff (byte-identical)
    Evidence: .omo/evidence/task-8-reproducibility-diff.txt

  Scenario: Sanity — total tokens is a positive integer
    Tool: Bash
    Steps:
      1. jq '[.[].tokens] | add' /tmp/opencode-audit/counts-system-prompt.json
    Expected Result: A positive integer (likely thousands to tens of thousands)
    Evidence: .omo/evidence/task-8-total.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-8-reproducibility-diff.txt`
  - [ ] `.omo/evidence/task-8-total.txt`

  **Commit**: NO (groups at end)

- [ ] 9. Run counter on tool-definition-category sources

  **What to do**:
  - From Task 6 output (`inventory-mcp-tools.json`), build a flat list of tool entries and save as `/tmp/opencode-audit/flat-tool-def.json` — shape: `[{label: "<server>.<tool>", content: "<description>\n<JSON.stringify(inputSchema)>"}]`. This is the contract input for the counter script's `--inventory` flag.
  - Run `/tmp/count_tokens.py --inventory /tmp/opencode-audit/flat-tool-def.json` against this list
  - Save counter output to `/tmp/opencode-audit/counts-tool-def.json` — sorted by `tokens DESC`
  - Each output entry: `{label: "<server>.<tool>", bytes, tokens, category: "tool-definition"}`

  **Must NOT do**:
  - Include system-prompt category sources here
  - Estimate tool counts — only count what Task 6 actually fetched
  - Skip tools silently — gaps from Task 6 must surface here as `gap` entries too

  **Recommended Agent Profile**:
  - **Category**: `quick` — flatten + count
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: 1, 6

  **References**:
  - Counter script: `/tmp/count_tokens.py`
  - Inventory: `/tmp/opencode-audit/inventory-mcp-tools.json`

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/counts-tool-def.json`
  - [ ] Each tool from Task 6 has either a count or a `gap` entry
  - [ ] Entries sorted by `tokens` descending
  - [ ] Reproducible: two runs produce byte-identical output

  **QA Scenarios**:

  ```
  Scenario: Happy path — tools counted, per-server subtotals computable
    Tool: Bash
    Steps:
      1. jq 'length' /tmp/opencode-audit/counts-tool-def.json
      2. jq 'group_by(.label | split(".")[0]) | map({server: .[0].label | split(".")[0], total: ([.[].tokens] | add)})' /tmp/opencode-audit/counts-tool-def.json
    Expected Result: Tool count matches Task 6's total; per-server totals printed
    Evidence: .omo/evidence/task-9-tool-totals.txt

  Scenario: Negative — gaps from Task 6 surface here
    Tool: Bash
    Steps:
      1. jq -r 'map(select(.gap != null)) | .[].label' /tmp/opencode-audit/counts-tool-def.json
    Expected Result: Lists any servers that couldn't be measured (e.g., pencil if app not running)
    Evidence: .omo/evidence/task-9-gaps.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-9-tool-totals.txt`
  - [ ] `.omo/evidence/task-9-gaps.txt`

  **Commit**: NO (groups at end)

- [ ] 10. Aggregate + ground-truth cross-reference

  **What to do**:
  - Combine `counts-system-prompt.json` and `counts-tool-def.json` into one master JSON `/tmp/opencode-audit/counts-master.json` with structure: `{system_prompt_total, tool_definition_total, grand_total, by_category: {...}, top_offenders: [...]}`
  - Compute top 10 offenders across both categories (highest individual token cost)
  - If Task 7 found assembled-system-prompt data in the DB, compute the count of that sample and add to the report as "Ground truth: assembled system prompt = N tokens" for cross-check against summed sources
  - Compute coverage ratio: `summed_sources / ground_truth` (if available). A ratio close to 1.0 = good coverage; far from 1.0 = significant unmeasured sources
  - Save to `/tmp/opencode-audit/counts-master.json`

  **Must NOT do**:
  - Fudge numbers to "match" ground truth
  - Hide unmeasured gaps — coverage ratio surfaces them by design
  - Reference quid project paths

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — aggregation, cross-reference logic, careful gap accounting
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 2 synthesis step)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 11
  - **Blocked By**: 7, 8, 9

  **References**:
  - Inputs: `counts-system-prompt.json`, `counts-tool-def.json`, `db-inspection.json`

  **Acceptance Criteria**:
  - [ ] File exists: `/tmp/opencode-audit/counts-master.json`
  - [ ] Contains keys: `system_prompt_total`, `tool_definition_total`, `grand_total`, `top_offenders` (length 10)
  - [ ] If ground truth available: includes `ground_truth_total` and `coverage_ratio` (float)
  - [ ] All totals are non-negative integers; `coverage_ratio` between 0 and ~1.5

  **QA Scenarios**:

  ```
  Scenario: Happy path — totals computed
    Tool: Bash
    Steps:
      1. jq '{sp: .system_prompt_total, td: .tool_definition_total, grand: .grand_total}' /tmp/opencode-audit/counts-master.json
    Expected Result: All three fields are positive integers; grand ≈ sp + td
    Evidence: .omo/evidence/task-10-totals.txt

  Scenario: Sanity — top offenders are real entries
    Tool: Bash
    Steps:
      1. jq '.top_offenders | length' /tmp/opencode-audit/counts-master.json
      2. jq '.top_offenders[0]' /tmp/opencode-audit/counts-master.json
    Expected Result: 10 entries; top offender has highest token count and a real label
    Evidence: .omo/evidence/task-10-top.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-10-totals.txt`
  - [ ] `.omo/evidence/task-10-top.txt`

  **Commit**: NO (groups at end)

- [ ] 11. Draft report skeleton (TL;DR, methodology, caveats, Sources Not Measured)

  **What to do**:
  - Create `.omo/reports/opencode-context-audit.md` with the following sections (filled in this task — counts table and recommendations come in Tasks 12-13):
    - **TL;DR**: 2-3 sentence summary of grand total tokens, biggest category
    - **Methodology**: How sources were enumerated, what tiktoken encoding was used, exact script invocation `uv tool run --with tiktoken python /tmp/count_tokens.py --inventory ...`
    - **Approximation Caveat**: Explicit paragraph stating cl100k_base is GPT-4's tokenizer; Anthropic's tokenizer is not public; numbers are ~±10-20% approximations useful for relative comparison, not absolute billing math
    - **Source Categories**: Definition of system-prompt vs tool-definition tokens (per Metis) and why they matter differently
    - **Sources Not Measured** (MANDATORY): Bulleted list of any source from any inventory's `gaps` array — each entry shows label + reason
    - Empty placeholder sections for "Per-Source Counts" (Task 12) and "Removal Recommendations" (Task 13)
  - Ensure path is `.omo/reports/opencode-context-audit.md` — create `.omo/reports/` dir if missing

  **Must NOT do**:
  - Include any token counts yet (filled in next task) — except references to the master totals
  - Reference quid project paths
  - Use generic phrases like "consider reviewing" or "this seems high" without numbers
  - Claim absolute accuracy

  **Recommended Agent Profile**:
  - **Category**: `writing` — markdown structure, clear methodology prose
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 3 synthesis)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12
  - **Blocked By**: 10

  **References**:
  - Aggregate output: `/tmp/opencode-audit/counts-master.json`
  - All gap arrays: `inventory-config.json`, `inventory-skills.json`, `inventory-plugin-injects.json`, `inventory-commands.json`, `inventory-mcp-tools.json`, `db-inspection.json`

  **Acceptance Criteria**:
  - [ ] File exists: `.omo/reports/opencode-context-audit.md`
  - [ ] Contains sections: TL;DR, Methodology, Approximation Caveat, Source Categories, Sources Not Measured
  - [ ] Methodology includes the exact `uv tool run` invocation
  - [ ] Approximation Caveat mentions cl100k_base + ±10-20% approximation
  - [ ] Sources Not Measured lists every entry from every inventory's `gaps` array

  **QA Scenarios**:

  ```
  Scenario: Happy path — required sections present
    Tool: Bash
    Steps:
      1. for section in "TL;DR" "Methodology" "Approximation Caveat" "Source Categories" "Sources Not Measured"; do grep -q "$section" .omo/reports/opencode-context-audit.md && echo "OK: $section" || echo "MISSING: $section"; done
    Expected Result: 5x "OK"
    Evidence: .omo/evidence/task-11-sections.txt

  Scenario: Negative — no generic AI-slop phrases
    Tool: Bash
    Steps:
      1. grep -iE "consider reviewing|seems high|may want to|potentially" .omo/reports/opencode-context-audit.md || echo "OK clean"
    Expected Result: "OK clean"
    Evidence: .omo/evidence/task-11-no-slop.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-11-sections.txt`
  - [ ] `.omo/evidence/task-11-no-slop.txt`

  **Commit**: NO (groups at end)

- [ ] 12. Fill per-source tables + category totals

  **What to do**:
  - Add to `.omo/reports/opencode-context-audit.md`:
    - **System-Prompt Sources Table**: markdown table with columns `Source | Path/Origin | Tokens | % of system-prompt total`, rows sorted by tokens DESC, totals row at bottom
    - **Tool-Definition Sources Table**: markdown table with columns `Server.Tool | Tokens | % of tool-def total`, rows sorted DESC, totals row
    - **Top 10 Offenders** (combined): cross-category table — `Rank | Source | Category | Tokens`
    - **Coverage Check** subsection: if Task 10 produced `ground_truth_total`, show `Summed sources: X | Assembled prompt: Y | Coverage: Z%` with one-sentence interpretation; otherwise note "ground-truth comparison not available (reason: ...)"
  - Every number must trace directly to `counts-master.json` — no hand-edited numbers

  **Must NOT do**:
  - Round numbers — show exact integers
  - Drop low-token sources to "simplify" — every measured source appears in its category table
  - Sort by anything other than tokens DESC (other orderings hide top offenders)

  **Recommended Agent Profile**:
  - **Category**: `writing` — markdown table generation, careful table formatting
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 3, sequential after Task 11)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 13
  - **Blocked By**: 11

  **References**:
  - `/tmp/opencode-audit/counts-master.json`, `counts-system-prompt.json`, `counts-tool-def.json`

  **Acceptance Criteria**:
  - [ ] Report contains "System-Prompt Sources" table with header row + ≥3 data rows + totals row
  - [ ] Report contains "Tool-Definition Sources" table (or a note explaining why no tool-def measurements were possible)
  - [ ] Report contains "Top 10 Offenders" cross-category table
  - [ ] Every count in tables matches the corresponding entry in `counts-master.json` (spot-check 5 random rows)
  - [ ] Coverage Check subsection exists

  **QA Scenarios**:

  ```
  Scenario: Happy path — tables present and numbers match source
    Tool: Bash
    Steps:
      1. grep -c "^|" .omo/reports/opencode-context-audit.md   # total markdown table rows
      2. # Pick a row from the report's system-prompt table and cross-reference against counts-system-prompt.json
      3. # e.g., for the top entry, label and tokens must match
    Expected Result: Multiple tables, spot-checked numbers match counts-master.json
    Evidence: .omo/evidence/task-12-table-spotcheck.txt

  Scenario: Negative — no rounded numbers
    Tool: Bash
    Steps:
      1. grep -E "\b[0-9]+[kK]\b" .omo/reports/opencode-context-audit.md || echo "OK no rounding"
    Expected Result: "OK no rounding" — no "10k", "5K" style rounding in counts (percentages can still use %)
    Evidence: .omo/evidence/task-12-no-rounding.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-12-table-spotcheck.txt`
  - [ ] `.omo/evidence/task-12-no-rounding.txt`

  **Commit**: NO (groups at end)

- [ ] 13. Write prioritized removal recommendations with explicit removal paths

  **What to do**:
  - Add to `.omo/reports/opencode-context-audit.md` a **Recommendations** section listing the top removal candidates, ordered by token savings
  - For each recommendation, provide:
    - **Source**: which source from the tables
    - **Tokens saved**: exact count (sum of removed entries)
    - **Category impact**: how much it reduces system-prompt-once vs tool-def-per-request totals
    - **Removal path** (MANDATORY): exact `file:line` to edit OR exact shell command (e.g., `npm uninstall --prefix ~/.config/opencode <package>`, or "Delete line X from `~/.config/opencode/opencode.json`", or "Remove symlink: `rm ~/.claude/skills/<name>`")
    - **Risk note**: One sentence describing what the user loses if removed (e.g., "loses ability to invoke /superpowers:* slash commands")
  - Group recommendations into tiers: **High-impact, Low-risk** | **High-impact, Medium-risk** | **Low-impact** (for completeness)
  - Conclude with a one-paragraph **Action Summary**: "If you apply [these N high-impact-low-risk removals], you save approximately T tokens per session prompt + S tokens per request"

  **Must NOT do**:
  - Make recommendations without removal paths (Metis: hard rule)
  - Use vague language: "consider removing", "may not need", "rarely used" (frequency is unknowable)
  - Recommend removing core OpenCode functionality (e.g., the Bash/Read/Write tools — these are essential)
  - Reference quid project paths

  **Recommended Agent Profile**:
  - **Category**: `writing` — prose recommendations grounded in numbers
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 3, sequential after Task 12)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: 12

  **References**:
  - `.omo/reports/opencode-context-audit.md` (existing skeleton + tables)
  - For removal paths:
    - Plugin removal: edit the `plugin` array in `~/.config/opencode/opencode.json` (current lines 16-20: opencode-claude-auth, oh-my-openagent, opencode-openai-codex-auth)
    - MCP removal: delete entry from `mcp` object in `~/.config/opencode/opencode.json` (pencil is at lines 4-14)
    - Skill removal: `rm ~/.claude/skills/<name>` (will remove the symlink, not the underlying repo)
    - Agent removal: edit `~/.config/opencode/oh-my-openagent.json` agents object
  - Per-source paths captured in inventories from Wave 1

  **Acceptance Criteria**:
  - [ ] Report contains "Recommendations" section
  - [ ] Every recommendation has a "Removal path" sub-field
  - [ ] Recommendations grouped into ≥2 tiers (high-impact, low-impact at minimum)
  - [ ] Action Summary paragraph at the end of the section
  - [ ] No occurrences of forbidden vague language ("rarely", "seldom", "often", "frequently", "consider", "may want")

  **QA Scenarios**:

  ```
  Scenario: Happy path — every recommendation has a removal path
    Tool: Bash
    Steps:
      1. # Count recommendation entries vs count of "Removal path:" lines — must be equal
      2. awk '/^### Recommendation/{r++} /Removal path:/{p++} END{print "recs:",r,"paths:",p}' .omo/reports/opencode-context-audit.md
    Expected Result: recs and paths are equal positive integers
    Evidence: .omo/evidence/task-13-recs-paths.txt

  Scenario: Negative — no fabricated frequency language
    Tool: Bash
    Steps:
      1. grep -iE "rarely|seldom|frequently used|often used|may want|consider removing" .omo/reports/opencode-context-audit.md || echo "OK clean"
    Expected Result: "OK clean"
    Evidence: .omo/evidence/task-13-no-frequency-fake.txt

  Scenario: Sanity — removal paths reference real files
    Tool: Bash
    Steps:
      1. grep -oE "~/.config/opencode/[a-zA-Z0-9./_-]+" .omo/reports/opencode-context-audit.md | sort -u | while read p; do test -e "${p/#\~/$HOME}" && echo "OK: $p" || echo "MISSING: $p"; done
    Expected Result: All cited paths exist on disk (no fabricated paths)
    Evidence: .omo/evidence/task-13-paths-exist.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-13-recs-paths.txt`
  - [ ] `.omo/evidence/task-13-no-frequency-fake.txt`
  - [ ] `.omo/evidence/task-13-paths-exist.txt`

  **Commit**: YES (final commit groups all tasks)
  - Message: `chore(audit): add OpenCode global context audit report`
  - Files: `.omo/reports/opencode-context-audit.md`, `.omo/evidence/**`
  - Pre-commit: re-run counter script and confirm report numbers still match

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read this plan end-to-end. For each "Must Have" item: verify the report or script demonstrates it (open `.omo/reports/opencode-context-audit.md` and check for: two separate token columns; Sources Not Measured section; reproducible script reference; removal paths on recommendations; symlink dedup explanation; cl100k_base caveat paragraph). For each "Must NOT Have": search for forbidden patterns — any modification of config files, any project-file references, fabricated frequency data, node_modules/ size reports, recommendations missing removal paths. Check evidence files exist in `.omo/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Read `/tmp/count_tokens.py`. Verify: no hard-coded fake counts, all numbers come from tiktoken, symlink resolution uses `os.path.realpath` or `stat().st_ino`, error handling for missing files/permissions, no `print` debug spam, clear function names. Run the script twice and diff outputs — must be byte-identical. Verify the script handles UTF-8 correctly. Check for AI slop in the report: excessive headings, repetitive phrasing, generic recommendations like "consider reviewing X" without specifics.
  Output: `Script runs [PASS/FAIL] | Reproducible [PASS/FAIL] | Slop check [N issues] | VERDICT`

- [ ] F3. **Manual QA of Report Content** — `unspecified-high`
  Execute the report's reproducibility claim: run `uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json` AND `--inventory /tmp/opencode-audit/flat-tool-def.json` (the flattened tool-definition inventory built in Task 9) from a clean shell, compare every number in the report against script output (allow for trivial sort order). Spot-check 3 recommendations: follow the cited removal path and verify it makes sense (e.g., if recommendation says "remove line 47 from opencode.json", open the file and confirm line 47 is the cited item). Verify "Sources Not Measured" entries each have a stated reason. Save evidence (terminal output + diffs) to `.omo/evidence/final-qa/`.
  Output: `Reproducibility [PASS/FAIL] | Recommendations spot-check [N/3 valid] | Sources Not Measured complete [PASS/FAIL] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  Verify the audit touched ONLY global sources. Grep the report and the `/tmp/opencode-audit/` inventories for any reference to `/Users/grant/dev/quid/.opencode/`, `/Users/grant/dev/quid/AGENTS.md`, or any other project path — must be ZERO matches. Verify no config files were modified: `cd ~/.config/opencode && git diff` (if it's a git repo) OR check mtimes haven't changed since plan start. Verify NO fabricated usage frequency data — search report for "frequently used", "rarely used", "often", "seldom" as red flags. Detect cross-task contamination by reviewing diffs across waves.
  Output: `Global-only [PASS/FAIL] | No config edits [PASS/FAIL] | No fake frequency [PASS/FAIL] | VERDICT`

---

## Commit Strategy

- **All tasks bundle as ONE commit** at the end (single deliverable: audit + script + recommendations).
- Message: `chore(audit): add OpenCode global context audit report`
- Files: `.omo/reports/opencode-context-audit.md`, `.omo/plans/opencode-context-audit.md` (already committed if user wants), `.omo/evidence/*` (gitignored typically)
- `/tmp/count_tokens.py` and `/tmp/opencode-audit/` are NOT committed (transient by design)
- Pre-commit: re-run script once to confirm reproducibility before commit

---

## Success Criteria

### Verification Commands
```bash
# Reproducibility (system-prompt category)
uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json > /tmp/sp-run1.json
uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/merged-system-prompt.json > /tmp/sp-run2.json
diff /tmp/sp-run1.json /tmp/sp-run2.json  # Expected: empty diff

# Reproducibility (tool-definition category — flattened tools inventory from Task 9)
uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/flat-tool-def.json > /tmp/td-run1.json
uv tool run --with tiktoken python /tmp/count_tokens.py --inventory /tmp/opencode-audit/flat-tool-def.json > /tmp/td-run2.json
diff /tmp/td-run1.json /tmp/td-run2.json  # Expected: empty diff

# Report integrity
test -f .omo/reports/opencode-context-audit.md && echo OK
grep -q "Sources Not Measured" .omo/reports/opencode-context-audit.md && echo OK
grep -q "cl100k_base" .omo/reports/opencode-context-audit.md && echo OK
grep -qE "system.prompt.*tool.def|tool.def.*system.prompt" .omo/reports/opencode-context-audit.md && echo OK

# No project file references in audit artifacts
! grep -rE "/Users/grant/dev/quid/(\.opencode/|AGENTS\.md)" .omo/reports/opencode-context-audit.md /tmp/opencode-audit/ && echo OK

# No fake frequency language
! grep -iE "frequently used|rarely used|seldom|often used" .omo/reports/opencode-context-audit.md && echo OK
```

### Final Checklist
- [ ] All "Must Have" items present in report
- [ ] All "Must NOT Have" items absent
- [ ] Counter script reproducible (byte-identical across runs)
- [ ] Every source has count OR Sources Not Measured entry
- [ ] Every recommendation has removal path
- [ ] tiktoken caveat stated
- [ ] User has reviewed and given explicit "okay"
