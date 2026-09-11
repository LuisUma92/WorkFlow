---
id: 20260911-latexzettel-detached-instance-errors
title: latexzettel returns/uses ORM objects after db_session closes (DetachedInstanceError) — render.note broken
type: bug
source_agent: user
opened_on: 2026-09-11

status: open
resolution:
priority: P1
severity: blocker

labels:
  - db
  - nvim
components:
  - latexzettel
  - workflow.nvim

adr_refs: ["LZK-0001", "LZK-0004", "0004"]
related_requests:
  - 20260910-c901-complexity-refactors
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - "`render_note` on a note that exists in the DB reaches the renderer call and persists the build timestamp (no DetachedInstanceError)."
  - "`render_updates` timestamp-based stale detection works on real DB notes."
  - "Objects returned in `ForceSyncResult.added_notes/updated_notes` and `AdjacencyMatrixResult.notes` are safe to read after the call (or the API returns plain data instead)."
  - "The characterization tests that currently pin the DetachedInstanceError are flipped to assert the working behaviour, in the same commit as the fix."
  - "RPC `render.note` works end-to-end from Neovim on an existing note (manual check with fake or real pdflatex)."
verification:
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q tests/latexzettel"
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py"
---

# Request: latexzettel uses ORM objects after `db_session` closes

## Context

Found 2026-09-11 while writing characterization tests for the C901 refactors
(`tasks/requests/2026-09-10-c901-complexity-refactors.md`). Pre-existing — not introduced by the
refactors; almost certainly a regression of the Peewee → SQLAlchemy port (LZK-0004), since Peewee
model instances were not bound to a session.

Mechanism: `latexzettel.infra.db.db_session` builds `Session(get_global_engine())` (default
`expire_on_commit=True`), commits and **closes** on `__exit__`. Any `Note` loaded inside the
`with` block and touched afterwards — a column or a lazy relationship — raises
`sqlalchemy.orm.exc.DetachedInstanceError`.

Affected call sites (pinned by passing characterization tests today):

| Where | Effect | Pinned by |
|-------|--------|-----------|
| `api/render.py` `render_note` — `note` loaded in `with db_session()`, then `_collect_note_references(note)` reads `note.labels`/`note.references` outside it | **every render of an existing note fails before the renderer runs**; exposed to Neovim via RPC route `render.note` (`server/routers.py:283,506`) | `test_render_biber_false_hits_detached_instance_bug`, `test_render_biber_true_hits_detached_instance_bug_before_biber_runs` |
| `api/render.py` `render_updates` — stale-note loop runs after the session closes | timestamp-based re-render never works | `test_timestamp_extension_branch_hits_detached_instance_bug` |
| `api/sync.py` `ForceSyncResult.added_notes/updated_notes` | returned objects unreadable by callers | `test_force_synchronize_characterization.py` (re-fetches as workaround) |
| `api/analysis.py` `AdjacencyMatrixResult.notes` | returned objects unreadable (the `adjacency` CLI only uses `len()`) | manual repro 2026-09-10 |

## Proposal

[UNCLEAR] Pick one — decide before coding:
1. **Keep the work inside the session**: restructure `render_note` so reference collection
   happens inside the `with db_session()` block and only plain data (filenames, references)
   leaves it. Most local, no global behaviour change.
2. **`expire_on_commit=False`** in `db_session`: fixes column reads after close but NOT lazy
   relationships (`note.labels`), so render would still fail unless relationships are eagerly
   loaded (`selectinload`). Global change — affects every latexzettel caller.
3. Return DTOs instead of ORM objects from the result dataclasses.

Option 1 (+3 for result types) is the conservative path.

## Other behaviours pinned during the same work (not bugs of this request; triage separately)

- `rename_reference`: a note containing `\excref{Old}` but with no `Link` row is not rewritten → dangling reference.
- `force_synchronize`: a brand-new `Note` gets no build dates even if html/pdf exist (needs a 2nd run);
  a `Note` found by reference under a different filename is silently re-pointed.
- `render_note` HTML path injects `external_documents` twice (duplicate `\externaldocument` lines).
- RPC server: missing `v` → error envelope reports the server's own version; only the first missing
  field is reported; a request with a non-str/int `id` gets no response at all (stderr only).

## Progress log

- 2026-09-11 — opened from the C901 characterization work; evidence re-checked by hand
  (`infra/db.py` Session construction + `render_note` load site + RPC route).
