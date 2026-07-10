---
# Required identity fields
id: 2026-07-09-sync-numeric-zettel-id-skip
title: "sync_vault/sync_note_files skip notes whose own id: is a bare-digit timestamp"
type: bug
source_agent: user
opened_on: 2026-07-09

# Lifecycle (mirrors GitHub issue states)
status: open
resolution:
priority: P2
severity: recurring-friction

# Scoping (GitHub-issue style labels)
labels:
  - notes
  - db
  - validation

components:
  - workflow.notes

# Linkage
adr_refs: ["ITEP-0013"]
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

# Implementation tracking
assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

# Acceptance
acceptance_criteria: []
verification: []
---

# Request: sync_vault/sync_note_files skip notes whose own `id:` is a bare-digit timestamp

## Context

`workflow notes sync` (`sync_vault` and `sync_note_files` in
`src/workflow/notes/sync.py`) reads a note's own `id:` frontmatter value and
guards it with `if not zettel_id or not isinstance(zettel_id, str): continue`
at three call sites: `src/workflow/notes/sync.py:503`, `:635`, `:695`.

`yaml.safe_load` parses a bare-digit timestamp id (e.g. `id: 202604010900`,
the legacy `LZK-0003` id convention still present in older/lecture-split
notes) as a Python `int`, not `str`. The `isinstance(zettel_id, str)` guard
then treats that note exactly like a note with no `id:` at all and silently
`continue`s past it — the note is never upserted, never gets a `Note` row,
and any edge that targets it (`derived_from_*`/`links_*` from another note)
stays permanently unresolved (`target_id = NULL`).

This is a sibling bug to the one fixed in F5
(`src/workflow/notes/edges.py::_coerce_zettel_id`, commit `41315a0`): that
fix coerces `str|int` (rejecting `bool`) for *target* zettel ids referenced
inside `derived_from_*`/`links_*` frontmatter values, so relation edges no
longer silently drop int-typed targets. This request is the mirror case —
the *source* note's own `id:` field — and was deliberately left unfixed
during F5 ("Known latent gap, unfixed and out of scope" per the F5 commit
message) because F5's scope was the relations frontmatter parser, not
`sync.py`'s note-discovery pass.

## Proposal

Apply the same `str|int` coercion (bool-rejecting) used in
`edges._coerce_zettel_id` to the `zettel_id = fm.get("id")` guard at all
three `sync.py` call sites, so a note whose `id:` YAML-parses as `int` is
still registered under its string form. Ideally factor a single shared
helper (e.g. reuse or extract `_coerce_zettel_id`) rather than duplicating
the coercion three times, per the ITEP-0013 single-source-of-truth
convention already established for the relation vocabulary.

### Commands / API surface

No new CLI surface — this is a fix inside the existing `workflow notes sync`
implementation. Affected entry points: `workflow notes sync`,
`workflow lectures split --sync` (calls `sync_note_files`).

### Shape of result

- A note with `id: 202604010900` (bare digits) is registered as a `Note`
  row with `zettel_id="202604010900"` after `workflow notes sync`, exactly
  as a note with `id: "202604010900"` (quoted) already is today.
- Existing behavior for notes with genuinely missing/blank `id:` is
  unchanged (still skipped).

## Acceptance criteria

- [ ] A note whose frontmatter has an unquoted bare-digit `id:` is upserted
      by both `sync_vault` and `sync_note_files`
- [ ] `bool` values for `id:` are still rejected (not coerced to `"True"`/`"False"`)
- [ ] Tests added under `tests/workflow/notes/test_sync.py` (or nearest
      existing sync test module) covering int-typed `id:` for both entry
      points
- [ ] Docs updated: CLAUDE.md sync bullet, if the coercion changes observable
      behavior worth noting there

## Out of scope

- Any change to `workflow.notes.edges` (`_coerce_zettel_id` for *target*
  ids) — already fixed in F5, commit `41315a0`.
- Any change to the flat relation frontmatter schema (ITEP-0013, F1-F7,
  commits `3060f9f`..`119327f`) — this request is purely about `sync.py`'s
  own-id discovery guard.
- Retroactively re-running sync for already-corrupted vault state — that is
  an operational step, not a code change.

## Evidence / glue replaced

```python
# src/workflow/notes/sync.py:503, :635, :695 — identical guard at each site
zettel_id = fm.get("id")
if not zettel_id or not isinstance(zettel_id, str):
    continue
```

- evidence: `src/workflow/notes/sync.py:503`, `:635`, `:695`
- sibling fix (target-id side): `src/workflow/notes/edges.py::_coerce_zettel_id`,
  commit `41315a0`
- frequency observed: not measured against the live vault; flagged as a
  known latent gap during the F1-F7 flat-relations-frontmatter work
  (2026-07-09), not from a reported incident

## Implementation notes

Read `_coerce_zettel_id` in `src/workflow/notes/edges.py` before
implementing — it already documents the `bool`-rejection rationale
(`isinstance(True, int)` is `True` in Python) and the `ZETTEL_ID_RE`
validation step. Whether to import and reuse that exact function from
`sync.py`, or extract a shared helper both modules import, is an open
design choice for the implementer; either satisfies the ITEP-0013
single-source-of-truth spirit, but duplicating the logic a third time does
not.

## Progress log

- 2026-07-09 — opened by user (flagged during ITEP-0013 F7 documentation
  pass as a known, previously-noted-but-unfixed gap; commit `41315a0`
  message calls it "Known latent gap, unfixed and out of scope")

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [ ] All acceptance criteria checked
- [ ] `verification` commands pass on master
- [ ] `implementation` frontmatter list filled with shipped paths/commands
- [ ] `closed_by` references commit/PR/ADR
- [ ] CLAUDE.md and ADR INDEX updated if architecture changed
- [ ] Related gap log entries cross-linked back to this request id
