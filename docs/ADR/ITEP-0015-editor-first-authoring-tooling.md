---
id: ITEP-0015
title: "Editor-first authoring tooling for the note graph"
aliases:
  - ADR-ITEP-0015
status: Accepted (2026-07-05, scope corrected)
date: 2026-05-22
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - notes
  - neovim
  - editor
  - cli
  - validation
decision_scope: cross-module
supersedes: null
superseded_by: null
related_adrs:
  - 0002-markdown-canonical
  - ITEP-0011-vault-unification
  - ITEP-0012-concept-orm
  - ITEP-0013-note-relation-graph
  - LZK-0001-jsonl-rpc-server
---

## Context

ITEP-0013 establishes human-first authoring of the note relation graph, with agents
as secondary consumers. The data model (`derived_from:`, `links:`, `relation_type`
enum, `zettel_id` references) is designed; the editor surface is not.

Without picker-backed insertion and in-buffer validation:

- Users must memorize the 9 `relation_type` values.
- Users hand-type 14-character `zettel_id` strings; typos surface only at
  `workflow validate notes --graph` time.
- Closed-set values (`relation_type`, `edge_class`) are duplicated in ORM, docs,
  and editor snippets — no single source of truth.

`nvim-plugin/workflow` already ships Snacks pickers for evaluations, items, courses,
and PRISMA. The pattern: CLI emits `--json`, plugin reads it once per session, user
invokes a keymap, plugin inserts at cursor or yanks to register.

This ADR extends that pattern to note graph primitives.

## Decision Drivers

- **Single source of truth** — enum lists from ORM CHECK constraints, surfaced via
  CLI, never duplicated in the editor.
- **Picker-friendly identifiers** — `zettel_id` values selected from a picker,
  never typed raw.
- **In-buffer validation** — errors visible before save as Neovim diagnostics.
- **CLI-equivalent validation** — every editor check MUST also run from
  `workflow validate notes --graph` for CI and pre-commit hooks.
- **Offline-first** — pickers query local DB; no network or LLM required.
- **Reuse existing plugin** — extend `nvim-plugin/workflow`, no parallel system.

## Proposed Surface

### A. CLI introspection endpoint

A new `workflow notes enums [--json]` command emits the closed-set values for the
note graph. The `--json` output follows a stable schema for editor consumption,
keyed by `edge_class`, `relation_type`, and `note_type`. The command MUST derive
its values from the same constants used by the ORM CHECK constraints and the
validation schema — never from a hand-maintained list.

A test gate compares the CLI output to the ORM CHECK definitions to catch drift
between the two.

The endpoint also exposes the canonical zettel_id format:

```json
{
  "zettel_id_format": {
    "library": "nanoid",
    "alphabet": "A-Za-z0-9_-",
    "default_length": 12,
    "min_length": 8,
    "max_length": 21,
    "validation_regex": "^[A-Za-z0-9_-]{8,21}$",
    "filename_convention": "<zettel_id>-<slug>.md",
    "alias_template": ["<zettel_id>-<slug>", "<slug>", "<zettel_id>"]
  }
}
```

### B. Listing endpoints

| Picker target | Backing CLI command | Status |
|---|---|---|
| note ID (zettel\_id + title) | `workflow notes list --json` | existing |
| relation\_type | `workflow notes enums --json` | new |
| edge\_class | `workflow notes enums --json` | new |
| bibkey | `workflow prisma bib list --json` | existing |
| concept code | `workflow concept list --json` | existing |

### C. Neovim picker keymaps

Proposed keymaps under the existing `<leader>w` prefix:

| Keymap | Action |
|---|---|
| `<prefix>er` | pick `relation_type`, insert at cursor |
| `<prefix>ec` | pick `edge_class`, insert at cursor |
| `<prefix>ei` | pick a note by zettel\_id, insert the id |
| `<prefix>eI` | pick a note, insert as full YAML `- id: …\n  type: …` item |
| `<prefix>eb` | pick a bibkey, insert |
| `<prefix>ek` | pick a concept code, insert |
| `<prefix>en` | generate and paste a fresh unique zettel\_id |

Pickers support both "insert at cursor" and "yank to register" modes via plugin
config; the keymap-to-mode mapping is user-configurable.

### D. In-buffer validation

`:WorkflowValidate` runs `workflow validate notes --graph <buffer-file>` on the
current file and surfaces results as Neovim diagnostics:

- ERROR — unknown `zettel_id` in `derived_from:` or `links:`
- ERROR — invalid `relation_type` (not in the closed set)
- WARN — lineage cycle introduced by the current buffer state
- WARN — orphan note without `entry_point: true`

The command runs automatically on `BufWritePost` for `.md` files inside the vault
root.

### E. Auto-fill primitives

`workflow notes new-id` emits a fresh, unique `zettel_id`. The `<prefix>en`
keymap pastes the output at cursor. YAML snippet expansions for `derived_from:`
and `links:` blocks are provided via the existing plugin; snippet ownership
(Lua-inline vs LuaSnip) is an open question deferred to implementation.

### F. Filename + alias convention (Obsidian compatibility)

Note files are named `<zettel_id>-<slug>.md` (e.g., `K3f5G7HEy_q2-gauss-law.md`).
This format is Obsidian-compatible: Obsidian resolves `[[...]]` against the
filename (minus `.md`) and against any value in the YAML `aliases:` list.

`workflow notes new` auto-populates `aliases:` with three forms for robust
wiki-link resolution:

```yaml
id: K3f5G7HEy_q2
title: Gauss's Law
aliases:
  - K3f5G7HEy_q2-gauss-law   # full filename
  - gauss-law                  # slug only (matches Obsidian's "shortest unique" default)
  - K3f5G7HEy_q2               # NanoID only (used by agents/tooling)
```

`notes sync` resolves wiki-links in this order:
1. `Note.zettel_id == target` (canonical)
2. `Note.alias == target` (Obsidian compat via alias index)
3. `Note.reference == target` (legacy `latexzettel` column)

Storing aliases requires a small schema addition (`note_alias` table with
`note_id` FK + `alias TEXT UNIQUE`). This is in-scope for the editor tooling
ADR because it directly enables the picker + author ergonomics, even though
the table itself is a `notes sync` concern.

## Architectural Rules (MUST)

- `workflow notes enums` output MUST be derived from the same source as the ORM
  CHECK constraints and validation schemas — never hand-maintained.
- Every picker MUST support both insert-at-cursor and yank-to-register modes.
- Every editor validation rule MUST have a CLI equivalent reachable from
  `workflow validate notes --graph`.
- The plugin MUST cache picker data per session; a `:WorkflowReloadEnums` command
  forces a refresh. Editing speed must not depend on a CLI roundtrip per keystroke.
- ITEP-0015 ships only after ITEP-0013 P2.1 (NoteEdge model) lands; the enum
  constants do not exist until then.

## Open Questions (defer to implementation phase)

1. ~~LSP vs ad-hoc diagnostics~~ — **RESOLVED 2026-05-22**: LSP is rejected for this
   domain. Industry pattern for knowledge-graph tools (Obsidian, Logseq,
   Org-roam, Foam, Dendron) is in-process or daemon-based completion, never
   LSP. Mature on-demand picker + on-save validation pattern is correct;
   no per-keystroke DB roundtrips. Multi-editor portability when needed
   goes via the existing LZK-0001 JSONL/NDJSON RPC server, not LSP.
2. ~~`zettel_id` format authority~~ — **RESOLVED 2026-05-22**: NanoID format
   locked. Alphabet `A-Za-z0-9_-`, default length 12, allowed range 8–21
   chars. Regex `^[A-Za-z0-9_-]{8,21}$`. Library: PyPI `nanoid`. Filename
   convention `<zettel_id>-<slug>.md`. Aliases auto-populated for Obsidian
   compatibility. Legacy Obsidian IDs (`YYYYMMDD-slug` style) match the
   regex and continue to validate — no migration required.
3. ~~Pre-commit hook semantics~~ — **RESOLVED 2026-07-05**: YES, shared exit
   codes. The CLI exit code (`workflow validate notes --graph`) is the CI
   authority; editor diagnostics are advisory only and never gate CI on their
   own.
4. ~~Multi-vault picker scope~~ — **RESOLVED 2026-07-05**: Single active vault
   via `resolve_vault_root()`. Multi-vault picker scope is deferred.
5. ~~Snippet ownership~~ — **RESOLVED 2026-07-05**: Lua-inline snippets.
   LuaSnip integration is deferred.

## Alternatives Considered

- **LLM-driven completion** — Deferred. ITEP-0013 establishes human-first authoring;
  agent completion cannot be the primary input method.
- **Hand-maintained enum lists in the plugin** — Rejected; violates ITEP-0013's
  single-source-of-truth rule.
- **Schema-form modal UI** — Possible future enhancement; current scope is
  cursor-level pickers only.

## Implementation Notes (high-level)

- `src/workflow/notes/cli.py` gains `enums` and `new-id` subcommands (reuses
  `get_engine_from_ctx`).
- `workflow.notes.constants` exports enum lists shared by ORM CHECK constraints
  and CLI introspection.
- Plugin: add `enums.lua`, `pickers/edges.lua`, `validate.lua` to
  `nvim-plugin/workflow/lua/workflow/`.
- Test gate: assert `workflow notes enums --json` matches ORM CHECK values.

## Compatibility / Migration

No DB or filesystem migration. Purely additive; existing pickers are unaffected.
Ships only after ITEP-0013 P2.1 (NoteEdge model) lands.

## Status

**Accepted (2026-07-05, scope corrected).** Drafted alongside ITEP-0013
acceptance. Implementation scheduled for ITEP-0013 Phase 2.3, or as a parallel
sub-track once P2.1 lands.

### Shipped subset (as of 2026-07-05)

Sections A/B/C-partial/D/E were already implemented under the "Wave 5 EDITOR"
label (`keymaps.lua:85`) **predating** this ADR's formal acceptance:

- `workflow notes enums --json` (`cli.py:590`)
- `workflow notes new-id` (`cli.py:645`)
- Pickers: `enums.lua`, `edges.lua`, `notes.lua`, `concepts.lua`
- Keymaps: `<prefix>en`, `<prefix>er`, `<prefix>ec`, `<prefix>eg`
- `BufWritePost` validation wiring (Section D)

This ADR is **accepted describing that work, not authorizing it anew.** The
true remaining delta is:

- `note_alias` table + migration — folded into the FTS `0017` migration per
  the W1 plan (see ADR-0021)
- Keymap wiring for `<prefix>ei`, `<prefix>eI`, `<prefix>eb`, `<prefix>ek`
- `notes capture` and `notes promote` commands (new; cross-ref the wave1
  plan)

## References

- ITEP-0013 — Note relation graph (data model; establishes the human-first
  principle this ADR fulfills)
- ITEP-0012 — Concept ORM (concept picker pattern)
- LZK-0001 — JSONL/NDJSON RPC server (existing plugin architecture)
- `nvim-plugin/workflow` — current pickers for evaluations, items, courses, PRISMA

## Change Log

| Date       | Change                                                                          |
| ---------- | ------------------------------------------------------------------------------- |
| 2026-05-22 | Initial draft — editor-first authoring tooling for the note graph. Spinoff from ITEP-0013 human-first reframing. |
| 2026-05-22 | Locked decisions: NanoID format (alphabet `A-Za-z0-9_-`, len 8–21, default 12); filename convention `<id>-<slug>.md` with auto-populated aliases for Obsidian compatibility; LSP rejected for this domain (multi-editor via LZK-0001 RPC server instead). Open Questions Q1 and Q2 resolved. |
| 2026-07-05 | F0 honesty amendment: Status Proposed → Accepted (2026-07-05, scope corrected). Added "Shipped subset" note — sections A/B/C-partial/D/E already implemented under the "Wave 5 EDITOR" label predating acceptance; this ADR accepts that prior work, it does not authorize it anew. True remaining delta: `note_alias` table+migration (folded into the 0017 FTS migration), keymap wiring `ei`/`eI`/`eb`/`ek`, and new `notes capture` + `notes promote` commands (cross-ref the wave1 plan). Open Questions Q3/Q4/Q5 resolved: shared exit codes (CLI is CI authority, editor advisory); single active vault via `resolve_vault_root`, multi-vault deferred; Lua-inline snippets, LuaSnip deferred. |
