---
id: 20260523-nvim-plugin-review-hardening
title: Harden nvim-plugin/lua/workflow/ — Lua review findings (4 HIGH + 8 MEDIUM)
type: enhancement
source_agent: claude
opened_on: 2026-05-23

status: open
resolution:
priority: P1
severity: recurring-friction

labels:
  - nvim
  - docs

components:
  - workflow.nvim
  - latexzettel

adr_refs: []
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release: v1.8.0
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - "Snacks global access guarded by pcall in all 3 picker files (no hard error when snacks.nvim missing)"
  - "latexzettel Lua tree marked deprecated — setup() prints deprecation notice; README updated"
  - "nvim-plugin/docs/cli-contracts.md exists with the 4 JSON shapes (notes.list, notes.show, notes.edges.list, notes.sync report) AND matching ---@class EmmyLua annotations in workflow.contracts module"
  - "nvim-plugin/doc/workflow.txt exists with :helptags-compatible tags for all 11 :Workflow* commands"
  - "Path traversal guard: vault-boundary check before vim.cmd('edit ...') and vim.fn.readfile() in picker/notes.lua, picker/edges.lua, notes.lua (uses config.is_in_workspace)"
  - "promote_note logic moved out of init.lua into notes.lua"
  - "Tag-token parsing extracted to notes.parse_tag_tokens — single source of truth across commands.lua, keymaps.lua, picker/notes.lua"
  - "picker/edges.lua confirm() delegates to require('workflow.notes').resolve_path() instead of inline notes show shell-out"

verification:
  - "nvim --headless -c 'lua require(\"workflow\").setup({})' -c 'qa' — no errors even with snacks.nvim absent"
  - "ls nvim-plugin/doc/workflow.txt nvim-plugin/docs/cli-contracts.md"
  - "grep -n '@class WorkflowNoteJSON\\|@class WorkflowEdgeJSON' nvim-plugin/lua/workflow/contracts.lua"
  - "grep -n 'promote_note' nvim-plugin/lua/workflow/init.lua — zero matches"
  - "grep -n 'parse_tag_tokens' nvim-plugin/lua/workflow/notes.lua — defined once"
  - "Manual: craft a frontmatter with path: /etc/passwd, run :WorkflowNotePicker, hit <CR> → vim.notify ERROR, no buffer opened"
---

# Request: Harden `nvim-plugin/lua/workflow/` — Lua review findings (4 HIGH + 8 MEDIUM)

## Context

After shipping the `workflow notes` Lua module + Snacks pickers in commit `a693f1b`, a 4-reviewer Lua review schema (idiom + security + architecture + test-readiness) ran in parallel against `nvim-plugin/lua/workflow/`. Findings: **0 CRITICAL, 4 HIGH, 8 MEDIUM, 6 LOW.** No secrets/credentials. No shell-injection (jobstart argv used consistently). But four structural HIGHs need closure before further plugin expansion:

1. **Bare `Snacks` global access** — hard Lua error if `snacks.nvim` not loaded. Three pickers affected (`picker/notes.lua:63`, `picker/edges.lua:59`, `picker/evaluations.lua:49`).
2. **Dual-plugin overlap** — `nvim-plugin/lua/workflow/` (CLI-based) and `src/latexzettel/lua/latexzettel/` (JSONL RPC) both expose `notes_new` / `notes_list_recent`. User confusion + divergent bugs ahead.
3. **Undocumented JSON contracts** — 4 different CLI `--json` shapes are decoded inline across 3 picker files with no single source of truth. Python CLI evolution will break the plugin silently.
4. **No `:help workflow.txt`** — 11 new `:Workflow*` commands undocumented. Zero discoverability.

Also several MEDIUM items: path-traversal via crafted frontmatter `path` field, business logic in `init.lua#promote_note`, token-parser duplication, picker confirm bypassing the action module.

Full review synthesis lives in chat history (4-agent run on 2026-05-23 between commits `a693f1b` and HEAD).

## Proposal

Single PR fixing the 4 HIGH items, the path-traversal MEDIUM, and the `promote_note` extraction. Other MEDIUMs deferred to a follow-up. Test scaffolding (Plenary + minimal_init + CI) is a separate request — NOT this one.

### Commands / API surface

No new user-facing commands. Only deprecation print added to `latexzettel`:

```text
[latexzettel] notice: the workflow.* plugin (nvim-plugin/) is now the
primary surface for note authoring. latexzettel.* commands will be
removed in v2.0.0; migrate to :WorkflowNote* equivalents.
```

### Shape of result

- `nvim-plugin/lua/workflow/contracts.lua` — new module exporting `---@class` definitions only; no runtime behavior.
- `nvim-plugin/docs/cli-contracts.md` — human-readable mirror of those types with example JSON bodies for each shape.
- `nvim-plugin/doc/workflow.txt` — Vim help format. Sections: SETUP, COMMANDS (one per `:Workflow*`), KEYMAPS, CONFIG, TROUBLESHOOTING.

## Acceptance criteria

(see frontmatter — duplicated here for visibility)

- [ ] Snacks global access guarded by `pcall(require, "snacks")` in all 3 picker files.
- [ ] `src/latexzettel/lua/latexzettel/init.lua#setup()` prints deprecation notice on first call.
- [ ] `nvim-plugin/lua/workflow/contracts.lua` with `WorkflowNoteJSON`, `WorkflowEdgeJSON`, `WorkflowSyncReportJSON`, `WorkflowEdgesCycleJSON` classes.
- [ ] `nvim-plugin/docs/cli-contracts.md` with the 4 JSON shapes.
- [ ] `nvim-plugin/doc/workflow.txt` with `:helptags`-compatible tags for all 11 new commands.
- [ ] Path-traversal guard wired through `config.is_in_workspace(path)` at every `vim.cmd("edit ...")` / `vim.fn.readfile(...)` site that consumes a CLI-supplied path.
- [ ] `promote_note` moved to `notes.lua`; `init.lua` retains only the re-export.
- [ ] `notes.parse_tag_tokens(input) → (add, remove)` defined once; reused in `commands.lua`, `keymaps.lua`, `picker/notes.lua`.
- [ ] `picker/edges.lua` `confirm()` delegates to `workflow.notes.resolve_path`.
- [ ] No regression: 1172 Python tests still pass.

## Out of scope

- Plenary test scaffolding + minimal_init.lua + CI yml — separate request.
- Refactoring `picker/*` 100-LOC `pick` functions into smaller pieces.
- Adding `notes edges show|resolve` Lua bindings.
- Removing `src/latexzettel/lua/latexzettel/` (deprecation now, deletion later).
- `setqflist` action-flag tidy and other LOWs.
- Job cancellation (`jobstop`) plumbing.

## Evidence / glue replaced

```text
# Hard Lua error on a fresh nvim install lacking snacks.nvim:
:WorkflowNotePicker
E5108: Error executing lua [string ":lua"]:1: attempt to index global 'Snacks' (a nil value)
```

```text
# Two ways to create a note today:
:LatexZettelNewNote      (RPC, via src/latexzettel/lua/)
:WorkflowNoteNew         (CLI, via nvim-plugin/lua/workflow/)
```

- evidence: `nvim-plugin/lua/workflow/picker/notes.lua:63` (bare Snacks)
- evidence: `src/latexzettel/lua/latexzettel/init.lua:80` vs `nvim-plugin/lua/workflow/notes.lua:N` (duplicate `notes.new` paths)
- evidence: `nvim-plugin/lua/workflow/picker/notes.lua:96`, `picker/edges.lua:117`, `notes.lua:213` (untrusted path → `:edit`)
- frequency observed: 1 review pass; expected ≥3 future drifts as CLI evolves without contract docs

## Implementation notes

- Match the existing `nvim-plugin/lua/workflow/picker/evaluations.lua` structural template — do not invent new picker patterns.
- For `contracts.lua`, mirror the Python source-of-truth: `src/workflow/notes/formatters.py` (notes list/show JSON), `src/workflow/notes/sync.py:SyncReport` (sync JSON), `src/workflow/notes/cli.py edges_check_cmd` (cycle JSON).
- Deprecation notice should fire ONCE per nvim session (use a module-level flag).
- `config.is_in_workspace(path)` may already exist in `config.lua`; verify before adding.
- `doc/workflow.txt` follow `:help write-plugin-help` convention; 78-col width, leader tags `*workflow*`, `*:WorkflowNoteSync*`, etc.

## Progress log

- 2026-05-23 — opened by claude after 4-reviewer Lua review schema on commit `a693f1b`

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [ ] All acceptance criteria checked
- [ ] `verification` commands pass on master
- [ ] `implementation` frontmatter list filled with shipped paths/commands
- [ ] `closed_by` references commit/PR/ADR
- [ ] CLAUDE.md updated if new top-level module added (`workflow.contracts`)
- [ ] Related gap log entries cross-linked back to this request id
