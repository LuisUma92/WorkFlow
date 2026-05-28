---
id:
title:
type:
source_agent: None
opened_on:

status: in_progress
phase_a_status: completed
resolution:
priority:
severity:

labels: []

components: []

adr_refs: []
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  -

verification:
  -
---

# Zettelkasten `main_topic` bundle — notes CRUD + frontmatter FK + graph filters

**Date filed:** 2026-05-04
**Source:** `~/Documents/01-U/.claude/gaps/requests/2026-05-03-*.md` (3 docs)
**Suggested labels:** `enhancement`, `cli`, `notes`, `graph`, `schema`, `zettelkasten`, `adr-itep-0009`

## Why bundled

Three gap reports filed 2026-05-03 form one dependency chain. Shipping them
piecemeal blocks the consumer (TikZ filtered export) and leaves the schema
half-done. Bundle them so the ADR + migration + CLI surface land as one
phased ITEP.

```
notes-crud  ──┐
              ├──►  note-frontmatter-main-topic  ──►  graph-export-tikz-filters
schema -------┘     (FK, validator, --strict)         (--main-topic, --depth, --cluster)
```

## Phase plan

### Phase A — `workflow notes` CRUD (unblocks user workflow)
Spec: `~/Documents/01-U/.claude/gaps/requests/2026-05-03-notes-crud-subcommands.md`

- Add subcommands: `new`, `list`, `show`, `tag`, `link` (keep `init`).
- Reuse `NoteFrontmatter` (`src/workflow/validation/schemas.py:40-51`).
- All mutating ops re-validate before write.
- JSON shape matches `course list --json` sibling.
- Tests: `tests/workflow/test_notes.py`.

### Phase B — `main_topic` field on frontmatter (schema + ADR ITEP-0009 Part II)
Spec: `~/Documents/01-U/.claude/gaps/requests/2026-05-03-note-frontmatter-main-topic.md`

- Extend `NoteFrontmatter` with optional `main_topic: str | None`,
  `discipline_area: str | None`.
- New validator `check_main_topic_against_db` (slug-or-id → `main_topic`
  table). Warn by default; error under `--strict-main-topic`.
- New validator `check_concepts_against_main_topic`
  (`Concept.main_topic_id == main_topic`).
- `workflow notes link <id> --main-topic <slug>` rewrites only that key.
- Backwards compatible: notes without `main_topic` continue to validate.
- Tests: `tests/workflow/test_validation_main_topic.py`.
- Schema migration: ITEP-0010 phase — add `note.main_topic_id` FK column +
  forward-only migration (no data backfill required, nullable).

### Phase C — `graph export-tikz` filter flags (consumer)
Spec: `~/Documents/01-U/.claude/gaps/requests/2026-05-03-graph-export-tikz-filters.md`

- New flags: `--main-topic`, `--discipline-area`, `--cluster`, `--depth`,
  `--include-tags`, `--exclude-tags`, `--layout`, `--color-by`.
- `--main-topic` and `--cluster` mutex → exit 2 on both.
- Wire `workflow graph clusters` output as input to `--cluster <name>`.
- `--color-by main_topic` hashes slug → stable palette.
- Tests: `tests/workflow/test_graph_export.py`.

## Hard dependencies

- Phase C blocked on Phase B (no `main_topic` → nothing to filter on).
- Phase B blocked on Phase A only for the `notes link --main-topic` round-trip
  test; the validator + schema can ship without CRUD.

## Acceptance (bundle level)

- [ ] All 3 phases ADR-tagged under ITEP-0009 + ITEP-0010 phase note.
- [ ] One PR per phase, merged in order A → B → C.
- [ ] End-to-end demo: `notes new` → `notes link --main-topic` →
  `graph export-tikz --main-topic <slug> --depth 1 -o out.tex` produces
  a compilable `.tex` with only that topic's induced subgraph.
- [ ] No regression in existing `validate notes` on legacy notes lacking
  `main_topic`.

## Out of scope

- Full TikZ palette redesign (Phase C uses simple hash-to-palette).
- Concept CRUD CLI (separate gap, not yet filed).
- Migration of existing notes to add `main_topic` (left to user / 01-U
  agents).

## Source gaps

- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-05-03-21:10`
- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-05-03-21:11`
- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-05-03-21:12`
- earlier: `2026-04-19-14:48` (notes stub re-raised)

## Status

`in_progress` — Phase A shipped. Phases B and C remain; B blocked on Topic
re-root migration (Phase 4D roadmap), C blocked on B.

## Progress Log

- **2026-05-27** — Phase A (`workflow notes` CRUD subcommands) shipped. [tbd]
  All five subcommands (`new`, `list`, `show`, `tag`, `link`) implemented with
  59 passing tests in `tests/workflow/test_notes.py`. Full service layer in
  `src/workflow/notes/service.py`; CLI in `src/workflow/notes/cli.py`.
  Re-validation before write is enforced. JSON shape mirrors `course list --json`.
  `phase_a_status: completed` set in frontmatter above.
