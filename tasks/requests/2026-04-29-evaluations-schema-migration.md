---
id: 2026-04-29-evaluations-schema-migration
title: Fix `workflow evaluations list` schema crash + add `db migrate` command
type: bug
source_agent: workflow-runner
opened_on: 2026-04-29
status: completed
priority: P0
severity: blocker
labels: [cli, db, validation]
components: [workflow.db, workflow.evaluation]
adr_refs: [ADR-0007, ITEP-0008]
related_requests: [2026-04-29-course-add-practice-quiz, 2026-04-29-main-topic-discipline-area-fk]
blocked_by: [2026-04-29-main-topic-discipline-area-fk]
resolution: implemented
closed_on: 2026-05-27
closed_by: Luis Fernando Umaña Castro
related_gaps:
  - "raw/workflow-runner.md#2026-04-27-14:20"
notes: |
  Primer.md confirms live DB at ~/.local/share/workflow/workflow.db is still
  pre-ITEP-0008 — `evaluations list` and other queries fail until migrated.
  Project has no Alembic; init_global_db calls metadata.create_all only.
  This request introduces the missing migration runner.
acceptance_criteria:
  - "workflow db migrate detects schema version, applies pending migrations, prints applied/skipped"
  - "--dry-run prints SQL without executing"
  - "evaluations list prints actionable 'Run: workflow db migrate' on OperationalError, no traceback"
  - "evaluations list exit code 1 on schema mismatch (not crash)"
  - "workflow db migrate idempotent (second run reports applied: [])"
  - "tests cover: graceful schema-mismatch, migrate adds column, dry-run, idempotent"
verification:
  - "pytest tests/workflow/db/test_migrate.py -v"
  - "pytest tests/workflow/evaluation/test_schema_mismatch.py -v"
---

# Fix `workflow evaluations list` schema crash + add `db migrate` command

## Summary

`workflow evaluations list --inst UCR --json` crashes with
`sqlite3.OperationalError: no such column: evaluation_template.description`.
The CLI query expects a column that was never created in the live database.
The entire `evaluations` group is therefore unusable until the schema is
manually corrected. There is no `workflow db migrate` command or schema-version
check to guide recovery.

## Motivation

- Reporting agent(s): workflow-runner
- Total occurrences: 1 (will recur on every fresh database or post-ADR-ITEP-0008
  install that has not been manually migrated)
- Severity: blocker
- Blocks / slows down: any query against the evaluations group; listing,
  filtering, or linking evaluations to courses is impossible until the
  schema is corrected

## Proposed CLI

```bash
# Fix 1: add missing column at schema level (migration)
workflow db migrate [--dry-run] [--json]

# Fix 2: graceful error message before SQL crash
workflow evaluations list [--inst <INST>] [--json]
```

- `workflow db migrate` : detects schema version, applies all pending
  migrations, reports what changed.
- `--dry-run` : prints SQL that would run without executing it.
- When a column is missing: instead of propagating the raw `OperationalError`,
  the CLI prints: "Database schema is out of date (missing: description on
  evaluation_template). Run `workflow db migrate` to upgrade." and exits 1.

## Example

```bash
# Before migration — graceful error instead of Python traceback
$ workflow evaluations list --inst UCR --json
Error: database schema out of date — missing column 'description' on
'evaluation_template'. Run: workflow db migrate

# After migration
$ workflow db migrate
Applied 1 migration(s): add_description_to_evaluation_template
$ workflow evaluations list --inst UCR --json
[{"id": 1, "institution": "UCR", "name": "PC04 FS0211 2026C1", ...}]
```

## Expected output shape

```json
// workflow db migrate --json
{
  "applied": ["0003_add_description_to_evaluation_template"],
  "skipped": [],
  "schema_version": 3
}

// workflow evaluations list --json
[
  {
    "id": 1,
    "institution_id": 2,
    "name": "PC04 FS0211 2026C1",
    "template_file": "eval/2026C1-G001-PC04.xml",
    "description": "Leyes del Movimiento II"
  }
]
```

Exit codes: 0 on success; 1 on schema error (with actionable message), missing
institution, or empty result set when `--fail-empty` is passed.

## Acceptance test

- `test_evaluations_list_schema_mismatch_graceful`: drop the `description`
  column on a test DB; `workflow evaluations list` exits 1 with a message
  containing "workflow db migrate", not a Python traceback.
- `test_db_migrate_adds_missing_column`: run `workflow db migrate` on a DB
  missing `description`; column is created; subsequent `evaluations list` exits 0.
- `test_db_migrate_dry_run`: `--dry-run` prints SQL without modifying the DB.
- `test_db_migrate_idempotent`: running `workflow db migrate` twice in a row
  exits 0 with `"applied": []` on the second run.

## Progress log

- **2026-05-27** — Implementation verified complete by Phase 3 review:
  - `src/workflow/db/errors.py`: `with_schema_guard` decorator fully implemented;
    translates `OperationalError` for missing column/table into `click.ClickException`
    with "workflow db migrate" hint; exit code 1; no traceback.
  - `src/workflow/evaluation/cli.py`: `@with_schema_guard` already applied to ALL
    commands (`eval_list`, `eval_show`, `eval_add`, `eval_edit`, `eval_rename`,
    `eval_add_item`, `eval_remove_item`, `item_list`, `item_taxonomy`, `item_add`,
    `course_list`, `course_add_practice`, `course_practices`, `course_add`).
  - `workflow db migrate` fully implemented: detects schema version, applies pending
    migrations, `--dry-run` (no stamp), `--json`, `status` subcommand, `--to` cap,
    idempotent on repeat runs.
  - New test file: `tests/workflow/evaluation/test_schema_mismatch.py` (5 tests):
    `test_evaluations_list_schema_mismatch_graceful`,
    `test_evaluations_list_missing_table_graceful`,
    `test_db_migrate_adds_missing_column`,
    `test_db_migrate_dry_run`,
    `test_db_migrate_idempotent` — all pass.
  - Full suite: 1292 passed, 3 skipped, 0 failures.

## Raw entries harvested

- `raw/workflow-runner.md#2026-04-27-14:20` — `workflow evaluations list`
  crashes on schema mismatch (missing `description` column)
