---
id: 20260703-exercise-failloud-validators
title: Fail-loud validators for exercise sync/parse (strict-concepts, status enum, unknown keys)
type: gap
source_agent: workflow-runner
opened_on: 2026-07-03

status: closed
resolution: implemented
priority: P0
severity: blocker

labels:
  - cli
  - validation
  - exercise
components:
  - workflow.exercise
  - workflow.validation

adr_refs: ["ADR-0010", "ITEP-0012"]
related_requests: []
related_gaps:
  - raw/workflow-runner.md#2026-06-14-10:00
  - raw/workflow-runner.md#2026-06-14-10:10
  - raw/workflow-runner.md#2026-06-14 (parse)
duplicates: []
blocked_by: []

assignee: claude
target_release: pre-candidatura-window-2026-07
implementation:
  - src/workflow/exercise/cli.py:377  # --strict-concepts
  - src/workflow/exercise/service.py  # sync_exercises strict wiring
  - src/workflow/exercise/parser.py:216-223  # explicit invalid status -> ParseResult.errors
  - src/workflow/validation/schemas.py:387-457  # validate_exercise_metadata unknown-key difflib warning
closed_on: 2026-07-03
closed_by: 7257024

acceptance_criteria:
  - "`workflow exercise sync PATH --strict-concepts` exits 1 when any concept code fails to resolve, listing every dropped code on stderr"
  - "Without the flag, behavior unchanged (warn + continue), but warning names the file and codes"
  - "An explicit invalid `status:` value in commented-YAML frontmatter causes parse/sync/validate to error (exit != 0) naming file, value, and valid enum; absent status still uses _infer_status"
  - "validate_exercise_metadata warns on unrecognized frontmatter keys with closest-match suggestion (difflib)"
  - "Tests added under tests/workflow/exercise/ covering all three behaviors"
  - "Docs updated: CLAUDE.md exercise CLI line"
verification:
  - "uv run pytest tests/workflow/exercise -q"
  - "uv run workflow exercise sync tests/fixtures/bad-concepts --strict-concepts; echo $?  # expect 1"
---

# Request: Fail-loud validators for exercise sync/parse

## Context

The costliest incident in the 2026 gap log was silent drift, not a missing
command: `status: solved` (invalid) was accepted silently → 11,301 files
normalized by hand afterward. Three silent-failure paths remain in the
exercise pipeline (audit `~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md`
§0, slugs #1–#3; council order-of-implementation #1):

1. `sync_exercises(..., strict_concepts=False)` exists in
   `src/workflow/exercise/service.py:80-84` and passes `strict` into
   `resolve_concepts` (service.py:163), but the CLI never exposes it —
   `_sync_files` (cli.py:67-69) always calls with default False. Unresolvable
   concept codes are dropped with a warning and exit 0 (5 codes lost in the
   2026-06-14 session).
2. An explicit invalid `status` silently falls back to `_infer_status`
   (`src/workflow/exercise/parser.py:216-223`); `status` is stripped before
   schema validation (parser.py:167-168) so it is never enum-checked.
3. `validate_exercise_metadata` (`src/workflow/validation/schemas.py:387-457`)
   reads keys only via `data.get(...)` — a `% contents:` typo for
   `% concepts:` is silently ignored.

## Proposal

Add fail-loud paths to existing commands. No new commands, no authoring-surface
changes (freeze-compatible).

### Commands / API surface

```bash
workflow exercise sync PATH --strict-concepts   # exit 1 on any unresolved concept code
workflow exercise sync PATH                     # unchanged, but warning lists file+codes
workflow validate exercise PATH                 # errors on invalid status enum; warns unknown keys
```

### Shape of result

- stdout: unchanged human report
- stderr: `error: invalid status 'solved' in <file> (valid: placeholder, in_progress, complete)`;
  `warning: unknown frontmatter key 'contents' in <file> — did you mean 'concepts'?`
- exit code 0 iff no strict violations and no invalid enum values

## Acceptance criteria

- [x] `--strict-concepts` on `exercise sync` → exit 1 + full dropped-code list
- [x] Invalid explicit `status` → hard error in parse/sync/validate; absent status keeps inference
- [x] Unknown frontmatter key → warning with difflib closest-match suggestion
- [x] Tests under `tests/workflow/exercise/` for all three
- [x] CLAUDE.md exercise CLI line updated

## Out of scope

- `concept.code` slug vs Spanish-label decision (audit #18 — user-deferred A/B/C
  architecture decision; do NOT resolve here)
- Auto-fix / normalization of any kind — this request only makes failures loud
- `lint-units` siunitx validation (audit P2/P3)

## Evidence / glue replaced

```bash
# manual post-hoc repair after silent acceptance of invalid enum:
# 11,301 files normalized by hand (session 2026-06-30, primer.md)
```

- evidence: `src/workflow/exercise/service.py:163-167`, `src/workflow/exercise/parser.py:216-223`, `src/workflow/validation/schemas.py:387-457`
- frequency observed: 1 catastrophic incident + 1 session with 5 silently dropped codes; recurs on every new bank sync

## Implementation notes

- Service layer already threads `strict`; CLI wiring is the whole job for item 1.
- Mirror `workflow notes sync --strict-concepts` UX (src/workflow/notes/cli.py:356-360).
- Status enum is `{placeholder, in_progress, complete}`; `_register_one` also
  defaults `status or "complete"` (cli.py:678) — keep that default for absent, error only on invalid explicit.

## Progress log

- 2026-07-03 — opened by claude from gap audit (slugs #1–#3) after live code verification
- 2026-07-03 — shipped as "Bundle A" (commit `7257024`, "feat(exercise): Bundle A — fail-loud validators")
- 2026-07-05 — closure annotation applied retroactively per `tasks/audit/2026-07-05-tasks-adr-completeness-audit.md` (Summary #3)

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [x] All acceptance criteria checked
- [x] `verification` commands pass on master
- [x] `implementation` frontmatter list filled with shipped paths/commands
- [x] `closed_by` references commit/PR/ADR
- [x] Related gap log entries cross-linked back to this request id
