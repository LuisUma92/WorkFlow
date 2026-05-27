# ITEP-0012 forward-dep closure — concept↔note DB linking

## Context

Per ADR ITEP-0012 and CLAUDE.md, the concept ORM is shipped:
- `Concept` + `NoteConcept` models live in `db/models/notes.py` (column rename to `concept_id` landed in migration 0008, v1.5.1).
- `workflow concept list|show|add|tree|rm|rename` CLI works.
- `workflow validate notes --strict-concepts` resolves frontmatter `concepts:` against the Concept table via `resolve_concepts()` in `workflow.concept.service`.
- `workflow notes link --concept CODE` already appends the code to the frontmatter `concepts:` list (idempotent, re-validated, byte-exact body) — `src/workflow/notes/cli.py:451–497` → `add_link()` in `src/workflow/notes/service.py:386–430`.

**What is missing — the closure:** no `NoteConcept(note_id, concept_id)` rows are ever created in the database. `notes link --concept` only touches the markdown frontmatter. `notes sync` (`src/workflow/notes/sync.py:303`) does NOT materialize `NoteConcept` rows from `fm.concepts` — there is no concept-sync pass. As a result, the M2M table is empty in live use, `concept rm --force` cascade-delete is a no-op for note linkage, and any graph query that joins through `note_concept` returns nothing.

**Intended outcome:** every validated `concepts:` code in a note's frontmatter materializes one `NoteConcept` row, idempotently, via two write paths: (a) the existing `notes link --concept` CLI flow, and (b) a new sync pass invoked by `workflow notes sync`. Unknown codes are reported as issues (not silently dropped) using the existing `resolve_concepts()` lenient/strict modes. No new migration needed.

## Scope

### Files to modify

- `src/workflow/notes/service.py` — extend `add_link()` to optionally accept a `session` and upsert the `NoteConcept` row when `concept` is given. Keep the frontmatter-only path working when `session` is `None` (back-compat).
- `src/workflow/notes/cli.py` — `link_cmd`: when `--concept` is given, open a session via `get_engine_from_ctx(ctx)` + `with Session(engine) as session`, pass it to `add_link()`, commit. Add `--remove` flag to symmetrically drop both the frontmatter entry and the `NoteConcept` row.
- `src/workflow/notes/sync.py` — add `_sync_note_concepts(session, note: Note, fm: NoteFrontmatter, *, strict: bool) -> tuple[int, list[dict]]` invoked per note inside `sync_vault`. Returns `(rows_upserted, issues)`. Wire its counters into the sync report.
- `src/workflow/notes/linker_ops.py` — new helper `upsert_note_concept(session, *, note_id, concept_id) -> bool` (returns True on insert, False on no-op). Mirrors the existing `upsert_note_edge()` shape.
- `src/workflow/concept/service.py` — leave `resolve_concepts()` alone; reuse it for both write paths.

### Reuse (no new code where it exists)

- `resolve_concepts(codes, session, *, strict)` — `src/workflow/concept/service.py:91–120`. Returns `(found, issues)`. Used by validator already; reuse verbatim.
- `upsert_note_edge()` — `src/workflow/notes/linker_ops.py`. Shape to mirror for `upsert_note_concept()` (PK conflict → no-op, no transaction churn).
- `get_engine_from_ctx(ctx)` — `src/workflow/db/engine.py`. Same pattern as `notes edges list/show/check/resolve`.
- `with_schema_guard` decorator — already on `link_cmd`; keep.

## Phased execution

### Phase 1 — DB write primitive + service extension
1. Add `upsert_note_concept(session, *, note_id, concept_id)` in `linker_ops.py`. Use `INSERT ... ON CONFLICT DO NOTHING` (SQLite dialect-aware). Idempotent.
2. Extend `add_link()` in `service.py`:
   - Signature: `add_link(root, note_id, *, concept=None, reference=None, exercise=None, session=None, strict=False, remove=False) -> tuple[Path, NoteFrontmatter, list[dict]]`. Third tuple element = issues from `resolve_concepts` (empty for non-concept paths).
   - When `concept` is given AND `session is not None`:
     - Look up the `Note` row by `zettel_id` (the frontmatter `id`). If missing, raise `NoteNotFound`.
     - Call `resolve_concepts([concept], session, strict=strict)`. If strict and unresolved → raise `NoteValidationError` BEFORE any disk write. If lenient and unresolved → append to issues, do NOT write frontmatter, return.
     - If resolved: upsert `NoteConcept`, then proceed with the existing frontmatter append.
   - When `remove=True`: drop `concept` from frontmatter (if present) AND delete the matching `NoteConcept` row (if both note + concept resolve). Idempotent on either half being absent.
3. Tests in `tests/workflow/test_notes_link.py` (new file) — strict miss, lenient miss, lenient hit, idempotent re-link, remove path.
4. Commit `feat(notes): link --concept materializes NoteConcept row — ITEP-0012`.

### Phase 2 — Sync pass
1. In `sync.py` `sync_vault()`, after the existing per-note label/citation/wikilink/edge passes, add a `concept_pass` that iterates `(note, fm)` and calls `_sync_note_concepts(session, note, fm, strict=strict)`.
2. The pass body:
   - If `fm.concepts` empty → skip.
   - `found, issues = resolve_concepts(list(fm.concepts), session, strict=strict)`.
   - For each `concept` in `found`: `upsert_note_concept(session, note_id=note.id, concept_id=concept.id)`. Count inserts.
   - Optionally: detect concepts that are linked in DB but NOT in frontmatter (stale rows) and prune them under `--prune` flag. Defer to a follow-up if it complicates the diff.
3. Extend the existing `SyncReport` dataclass with `concept_links_created: int` and `concept_issues: list[dict]`. Update the table/JSON formatter rows.
4. Tests in `tests/workflow/test_notes_sync_concepts.py` (new file) — fresh sync, idempotent re-sync, strict mode rejects unknown code, lenient mode warns + skips.
5. Commit `feat(notes): sync materializes NoteConcept rows — ITEP-0012 P2`.

### Phase 3 — Docs + ADR closure
1. ADR `docs/ADR/ITEP-0012-concept-orm.md` — flip status to **Implemented (date)**, add a 4-line retrospective listing the two commits.
2. CLAUDE.md ADR table row for ITEP-0012 → `Implemented`. Update the `notes link --concept` bullet to mention DB linkage + `--remove`.
3. `~/.claude/primer.md` — append milestone `✅ v1.7.0 — ITEP-0012 forward-dep closure`; drop the ITEP-0012 line from "Next step".
4. Commit `docs(adr): ITEP-0012 Implemented — concept-to-note DB linking`. Tag `v1.7.0`. Do NOT push.

## Verification (end-to-end)

```bash
# Phase 1 + 2
pytest --ignore=tests/test_database.py -x
pytest tests/workflow/test_notes_link.py tests/workflow/test_notes_sync_concepts.py -v

# Live smoke (after manual commit + migrate already done)
workflow concept list --json    # confirm at least one concept exists
workflow notes link <some-note-id> --concept forces
python -c "
import sqlite3
c=sqlite3.connect('/home/luis/01-U/workflow/workflow.db')
for r in c.execute('SELECT note_id, concept_id FROM note_concept'): print(r)
"
# Then re-run with --remove and confirm the row disappears.
workflow notes sync          # confirm 'concept_links_created' line in the report
```

## Risks

| Risk | Mitigation |
|------|------------|
| `add_link()` signature change may break existing CLI callers | The `session` kwarg defaults to `None` — frontmatter-only path stays back-compat |
| Sync pass slow on large vaults (per-note `resolve_concepts` query) | Batch: collect all unique codes across vault first, resolve once, then upsert per note. Implement only if a measurable test shows it |
| Strict vs lenient default | Match the validator default (lenient at sync; strict opt-in via `--strict-concepts` flag on `notes sync`) — surface as warnings in the report |
| `NoteConcept` rows orphaned when frontmatter drops a code | Phase 2 prune is deferred; document as known limitation in ADR retrospective |

## Out of scope (defer)

- Prune of stale `NoteConcept` rows when frontmatter no longer lists the code (separate `--prune` ITEP).
- Knowledge graph extension to emit `note→concept` GraphEdges (analogous to ITEP-0013 P2.6 for NoteEdges). Land in a follow-up phase.
- LZK-0004 already shipped (v1.6.0). LZK-0001/0002 untouched.
