## [2026-05-26] Task: T2 - Config inventory
- Files found: opencode.json (6627 bytes), oh-my-openagent.json (4027 bytes), tui.json (48 bytes)
- Total bytes: 10702

## 2026-05-27
- Created `/tmp/count_tokens.py` for deterministic token audits with `tiktoken.get_encoding("cl100k_base")`.
- `--inventory` reads JSON from a file, `--inline` reads JSON from stdin, and output is sorted by tokens desc then label asc.
- Path-based entries dedupe by realpath inode; symlink duplicates are skipped after the first seen file.
- Missing/unreadable paths return structured error objects instead of crashing.

## 2026-05-27 Task: T7 - DB schema + CLI debug flags
- DB: `~/.local/share/opencode/opencode.db` (Drizzle ORM / SQLite, ~70MB)
- 16 tables: message, part, session, session_message, todo, project, workspace, event, event_sequence, account, account_state, control_account, permission, session_share, data_migration, __drizzle_migrations
- No dedicated `system_prompt` column. System/context content is embedded inside the JSON `data` blob of `message` rows.
- `message.data` is a JSON string with keys: role, parentID, mode, agent, tools, time, etc. 145 messages contain a `"system"` key; 2 contain `"system_prompt"` key.
- Message roles: assistant (4717), user (440) — no explicit `system` role rows.
- Part types (21876 total): tool (7396), step-start (4617), step-finish (4580), reasoning (3392), text (1428), patch (443), file (13), compaction (7).
- Max system-containing message blob: ~58K chars ≈ ~14.5K tokens; system_prompt blobs: 61K–64K chars.
- CLI debug flags found: `--print-logs`, `--log-level [DEBUG|INFO|WARN|ERROR]`, `opencode debug` subcommand (config, info, paths, agent, skill, snapshot, startup, lsp, rg, file, scrap, v2, wait), `opencode export [--sanitize]`, `opencode db [query]` (direct SQL access).
- `opencode export --sanitize` redacts sensitive transcript/file data — relevant for privacy audits.
- Evidence: `/Users/grant/dev/quid/.omo/evidence/task-7-db-schema.txt` (16 tables, system_prompt_column=true) and `task-7-no-pii.txt` (OK clean).

## 2026-05-27 Task: T5 - Command inventory
- Plugin command files live under `~/.claude/plugins/cache/` (NOT `~/.config/opencode/node_modules/`).
- `~/.config/opencode/node_modules/` only contains runtime SDK deps (zod, effect, yaml, etc.) — no skill/command files.
- `~/.claude/plugins/installed_plugins.json` is the authoritative source for which plugin version is active.
- Active plugin versions confirmed: superpowers@5.1.0 (claude-plugins-official), document-skills@690f15cac7f7 (anthropic-agent-skills), code-review@unknown (claude-plugins-official), frontend-design@unknown (claude-plugins-official), frontend-design@1.0.0 (claude-code-plugins — also installed, shadowed).
- superpowers skills are SKILL.md files under `skills/<name>/SKILL.md` within the plugin cache.
- document-skills skills follow the same pattern; claude-api skill added in ≥690f15cac7f7 (absent in 3d5951151859).
- code-review is a command (not a skill): stored under `commands/code-review.md` with frontmatter `allowed-tools`, `description`, `disable-model-invocation`.
- User-scope skills: `/homelab` → `~/.claude/skills/homelab/SKILL.md`; `/swiftui-skills` → `~/.agents/skills/swiftui-skills/SKILL.md`.
- Built-in commands (playwright, frontend-ui-ux, git-master, review-work, ai-slop-remover, commit, init-deep, ralph-loop, ulw-loop, cancel-ralph, refactor, start-work, stop-continuation, remove-ai-slops, handoff, hyperplan) have no source file in the plugin tree — baked into the opencode binary.
- Total: 35 sourced entries + 16 builtin gaps = 51 commands in scope.
- Evidence: `/Users/grant/dev/quid/.omo/evidence/task-5-commands.txt` and `task-5-builtins.txt`.

## 2026-05-27 Task: T6 - MCP tool schema inventory
- Only `pencil` is explicitly registered in `~/.config/opencode/opencode.json` as an MCP server.
- `oh-my-openagent.json` has an empty `mcp: {}` block — no additional servers registered there.
- 3 additional `@modelcontextprotocol` servers discovered in `~/.npm/_npx/` cache (previously installed via npx, not in opencode's config):
  - `server-filesystem` v2025.3.28 (`~/.npm/_npx/a3241bba59c344f5`)
  - `server-sequential-thinking` v2025.7.1 (`~/.npm/_npx/de2bd410102f5eda`)
  - `server-brave-search` v0.6.2 (`~/.npm/_npx/be9bcbed6978f068`)
- Live `tools/list` results:
  - `pencil`: 13 tools (batch_design, batch_get, export_nodes, find_empty_space_on_canvas, get_editor_state, get_guidelines, get_screenshot, get_variables, open_document, replace_all_matching_properties, search_all_unique_properties, set_variables, snapshot_layout) — binary launches without Pencil.app running
  - `server-filesystem`: 11 tools (read_file, read_multiple_files, write_file, edit_file, create_directory, list_directory, directory_tree, move_file, search_files, get_file_info, list_allowed_directories)
  - `server-sequential-thinking`: 1 tool (sequentialthinking)
  - `server-brave-search`: GAP — requires `BRAVE_API_KEY` env var, crashes on startup
- The many tools visible in session (Ast_grep_*, Background_*, Context7_*, Lsp_*, etc.) come from oh-my-openagent/opencode plugins loaded as JavaScript (not as separate MCP server processes).
- `@opencode-ai/plugin` dist/tool.js only exports a `tool()` wrapper — plugins add tools via JS API inside opencode, not via MCP subprocess.
- MCP protocol: full init handshake required (`initialize` → `notifications/initialized` → `tools/list`); bare `tools/list` without init may not respond.
- Evidence: `/Users/grant/dev/quid/.omo/evidence/task-6-mcp-counts.txt` and `task-6-mcp-gaps.txt`.
