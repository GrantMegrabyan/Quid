## 2026-05-20 Task: orchestration-init
- Execute plan directly in current project directory; no worktree path is present in `.omo/boulder.json`.
- Category names are case-insensitively unique after trimming, per plan default.
- `Uncategorized` is seeded, neutral, non-deletable; deleting other categories cascades expenses to `UNCATEGORIZED_ID`.
