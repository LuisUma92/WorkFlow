---
id: 20260703-exercise-composability-flags
title: exercise sync --json/--status/--dry-run + exercise list --concept
type: gap
source_agent: workflow-runner
opened_on: 2026-07-03

status: closed
resolution: implemented
priority: P0
severity: recurring-friction

labels:
  - cli
  - exercise
  - db
components:
  - workflow.exercise
  - workflow.db

adr_refs: ["ADR-0010", "ITEP-0012"]
related_requests: ["2026-04-29-exercise-list-json-filters"]
related_gaps:
  - raw/workflow-runner.md#2026-06-14
  - raw/note-curator.md#2026-06-26
duplicates: []
blocked_by: []

assignee: claude
target_release: pre-candidatura-window-2026-07
implementation:
  - src/workflow/exercise/cli.py  # sync --json/--dry-run/--status; list --concept
  - src/workflow/exercise/service.py:163-167  # dropped_concepts surfaced, not recomputed
closed_on: 2026-07-03
closed_by: 39e4d6f

acceptance_criteria:
  - "`workflow exercise sync PATH --json` emits machine-readable report incl. synced/skipped/errors and dropped_concepts list"
  - "`workflow exercise sync PATH --dry-run` parses and reports the diff without any DB writes"
  - "`workflow exercise sync PATH --status <enum>` filters which files get synced by parsed status"
  - "`workflow exercise list --concept <code>` filters via ExerciseConcept M2M join; composes with existing flags"
  - "Tests under tests/workflow/exercise/ for each flag"
  - "--json parity with sibling commands (list already has it)"
verification:
  - "uv run pytest tests/workflow/exercise -q"
  - "uv run workflow exercise sync tests/fixtures/bank --dry-run --json | jq .dropped_concepts"
  - "uv run workflow exercise list --concept ley-de-gauss --json"
---

# Request: exercise sync/list composability flags

## Context

Cara 3 of the transversal analysis (`~/01-U/.claude/gaps/2026-07-03-transversal-gap-analysis.md`):
the CLI can't be scripted because output isn't machine-readable and key filters
are missing. Live verification (2026-07-03) confirmed the only two genuinely
open P0s in that section:

- `exercise sync` (src/workflow/exercise/cli.py:246-264) takes only a `PATH`
  positional — no `--json`, `--status`, `--dry-run`.
- `exercise list` (cli.py:183-199) has `--status/--difficulty/--taxonomy-level/
  --type/--course/--limit/--json` but no `--concept`; `repo.find_by_filters`
  (cli.py:215) receives no concept arg.

The missing `--concept` lookup nearly caused a real content error: semana04
almost linked Corriente Alterna examples instead of Magnetismo de Materia
(raw/note-curator.md#2026-06-26) — priority driven by risk, not just friction.

## Proposal

Extend the two existing commands; no new commands.

### Commands / API surface

```bash
workflow exercise sync PATH [--json] [--dry-run] [--status placeholder|in_progress|complete]
workflow exercise list --concept <code> [existing flags...]
```

Expected output / JSON shape (sync --json):

```json
{
  "synced": 12, "skipped": 3, "errors": [],
  "dropped_concepts": [{"file": "…", "codes": ["…"]}],
  "dry_run": true
}
```

### Shape of result

- exit code 0 iff no errors (dry-run never writes, still exits 0 on clean parse)
- `--json` emits single object (sync) / array (list), no ANSI noise on stdout

## Acceptance criteria

- [x] `sync --json` with `dropped_concepts` field
- [x] `sync --dry-run` provably writes nothing (test asserts DB row counts unchanged)
- [x] `sync --status` filter
- [x] `list --concept` via ExerciseConcept M2M; unknown code → exit 2 with clear message
- [x] Tests under `tests/workflow/exercise/`
- [x] Docs updated: CLAUDE.md command table

## Out of scope

- `--chapter` filter (needs BibContent locus join — separate, lower priority)
- Any glob/batch transform surface (R4 marco, post-candidatura)

## Evidence / glue replaced

```bash
# agent re-parsing human sync output to detect dropped codes; manual DB spot-checks
```

- evidence: `src/workflow/exercise/cli.py:183-199,246-264`
- frequency observed: every bank sync; 1 near-miss content error (semana04)

## Implementation notes

- `dropped_concepts` data already produced at service.py:163-167 warnings — surface, don't recompute.
- `list --concept`: join ExerciseConcept + Concept.code (models in db/models/exercises.py); reuse `resolve_concepts` from workflow.concept.service for validation (strict=True).
- Supersedes the remaining open sliver of `2026-04-29-exercise-list-json-filters.md` (rest shipped; close that file pointing here).

## Progress log

- 2026-07-03 — opened by claude from gap audit (slugs #6, #7) after live code verification
- 2026-07-03 — shipped as "Bundle B" (commit `39e4d6f`, "feat(exercise): Bundle B — sync --json/--dry-run/--status + list --concept")
- 2026-07-05 — closure annotation applied retroactively per `tasks/audit/2026-07-05-tasks-adr-completeness-audit.md` (Summary #4)

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [x] All acceptance criteria checked
- [x] `verification` commands pass on master
- [x] `implementation` frontmatter list filled
- [x] `closed_by` references commit/PR/ADR
- [x] Related gap log entries cross-linked back to this request id
