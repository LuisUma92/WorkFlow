---
# Required identity fields
id: 20260910-accept-to-note-atomic-create
title: Atomic create for literature-note writes (TOCTOU in accept_to_note)
type: bug
source_agent: user
opened_on: 2026-09-10

# Lifecycle
status: closed
resolution: implemented
priority: P2
severity: polish

labels:
  - cli
  - prisma
  - notes
  - security
components:
  - workflow.prisma
  - workflow.notes

# Linkage
adr_refs: ["0020"]
related_requests:
  - 20260603-prisma-to-literature-note
related_gaps: []
duplicates: []
blocked_by: []

# Implementation tracking
assignee: unassigned
target_release:
implementation:
  - "src/workflow/prisma/accept_to_note.py — exclusive create via Path.open('x'), FileExistsError → created=False"
  - "tests: test_note_created_concurrently_is_not_overwritten, test_concurrently_created_notes_counted_skipped"
closed_on: 2026-09-10
closed_by: "fix(prisma): exclusive create for literature notes (2026-09-10)"

# Acceptance
acceptance_criteria:
  - "`accept_to_note` creates the note with exclusive-create (`open(path, \"x\")` / `O_EXCL`), not `exists()` + `write_text()`."
  - "A pre-existing file at `note_path` is never overwritten — `FileExistsError` maps to `created=False` (same result shape as today's skip)."
  - "Bulk `--all-accepted` counts a `FileExistsError` as `skipped`, never as an error or a crash."
  - "`--dry-run` still writes nothing and still reports `created=False` for an existing file."
  - "`workflow notes create --type literature` (reuses `accept_to_note`) inherits the fix with no separate code path."
verification:
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q tests/workflow/prisma/test_accept_to_note.py"
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py  # baseline 2627 passed, 3 skipped"
  - "uv run flake8 src/workflow/prisma/accept_to_note.py --max-line-length=127 --max-complexity=10  # no new findings vs HEAD"
---

# Request: Atomic create for literature-note writes (TOCTOU in accept_to_note)

## Context

Security review `tasks/security/2026-06-03-roadmap-new-surfaces.md` finding **#4 [MEDIUM]**
asked for atomic create on the idempotent note write. Re-verified 2026-09-10 against code — still
open. `src/workflow/prisma/accept_to_note.py:301-311`:

```python
if note_path.exists():                     # check
    return AcceptToNoteResult(..., created=False, ...)
if not dry_run:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")   # use — truncates if file appeared meanwhile
```

Between the `exists()` check and `write_text()` another process (a second CLI run, the nvim
`:WorkflowPrismaAcceptToNote` command, `workflow notes create`, or an editor saving the same
`<YYYYMMDD>-lit-<bibkey>.md`) can create the file; `write_text` then **silently overwrites** it —
the one outcome the idempotency contract promises never happens.

Impact is local-only (single-user vault, no privilege boundary), hence MEDIUM/polish, but the
failure mode is silent data loss of a hand-edited note.

## Proposal

Replace check-then-write with exclusive create:

```python
if not dry_run:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with note_path.open("x", encoding="utf-8") as fh:
            fh.write(content)
    except FileExistsError:
        return AcceptToNoteResult(note_path=note_path, bibkey=resolved_bibkey,
                                  created=False, content=content)
```

Keep the `exists()` early-return only for the `dry_run` branch (it writes nothing, so it cannot
race destructively). Result shape and JSON contract (`{"note_path","bibkey","created"}`) unchanged.

## Out of scope

- Findings #5 (LOW, bib-block brace balance) — separate.
- Locking across the DB sync that follows the write.

## Implementation notes

- TDD: RED test pre-creates `note_path` *after* the path is computed but before the write — simplest
  via monkeypatching `Path.exists` to return `False` while the file exists — and asserts the original
  content survives and `created is False`.
- Bulk path (`accept_all`, `accept_to_note.py:370-395`) already treats `created=False` as skipped;
  confirm with a test, don't add a new branch.

## Progress log

- 2026-09-10 — opened by user from security review 2026-06-03 #4 (re-verified open during
  `tasks/audit/2026-09-10-tasks-and-primer-audit.md`).
- 2026-09-10 — **closed.** TDD: 2 race tests (single + bulk, `Path.exists` monkeypatched to miss
  the file) went RED with the overwrite (`created=2`), GREEN after the fix. The `exists()`
  early-return was dropped entirely: dry-run always reported `created=False` anyway, so it needs
  no probe. Suite 2629 passed / 3 skipped (baseline 2627 + 2). Real-CLI smoke on a scratch
  DB + vault: `notes create --type literature` → `created:true`; file overwritten with a sentinel;
  second run → `created:false`, sentinel intact.
