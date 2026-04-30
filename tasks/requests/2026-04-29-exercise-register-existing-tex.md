---
id: 2026-04-29-exercise-register-existing-tex
title: Add `workflow exercise register` to import existing .tex files
type: feature
source_agent: exam-author
opened_on: 2026-04-29
status: open
priority: P0
severity: blocker
labels: [cli, db, exercise]
components: [workflow.exercise, workflow.db]
adr_refs: [ADR-0010, ADR-0011]
related_requests: [2026-04-29-exercise-list-json-filters]
related_gaps:
  - "raw/exam-author.md#2026-04-23"
notes: |
  workflow exercise create only scaffolds new placeholder. Need a separate
  `register` (and batch glob) verb that ingests an existing .tex with
  UCIMED-specific metadata (SCM/SSU/SDE) and writes one row per file.
  Type enum extension lives in src/workflow/exercise/cli.py:211 (_EXERCISE_TYPES).
acceptance_criteria:
  - "workflow exercise register --path --type --course --cycle --partial --domain --points [--taxonomy-level] [--taxonomy-domain] [--json] inserts row"
  - "type enum extended with SCM, SSU, SDE"
  - "register-batch '<GLOB>' --course --cycle --partial registers every match"
  - "--json emits list of {id, registered, db_row_id, path, course, cycle, partial, type}"
  - "exit 1 on collision with 'already registered'"
  - "exit 1 on missing path with 'not found'"
  - "exit 1 on unknown --type value"
verification:
  - "pytest tests/workflow/exercise/test_register.py -v"
  - "pytest tests/workflow/exercise/test_register_batch.py -v"
---

# Add `workflow exercise register` to import existing .tex files

## Summary

`workflow exercise create` only scaffolds a new placeholder file; it cannot
point to an existing `.tex` at a given path or accept UCIMED-specific metadata
(`SCM`, `SSU`, `SDE` types; `--course`, `--cycle`, `--partial`, `--domain`,
`--points`). Every parcial build that produces new exercise files ends with zero
DB registrations, breaking any downstream query or Moodle export that depends on
the exercise index.

## Motivation

- Reporting agent(s): exam-author
- Total occurrences: 1 session (31 files unregistered); will recur every future
  parcial build
- Severity: blocker
- Blocks / slows down: post-authoring DB registration for UCIMED parciales;
  `workflow exercise list --course CB0009` returns nothing even after files exist

## Proposed CLI

```bash
workflow exercise register --path <TEX_PATH> \
  --type <SCM|SSU|SDE|multichoice|shortanswer|essay|numerical|truefalse> \
  --course <COURSE_CODE> \
  --cycle <CYCLE>          \  # e.g. 2026C1
  --partial <PARTIAL_ID>   \  # e.g. P02
  --domain <DOMAIN_SLUG>   \
  --points <N>             \
  [--taxonomy-level <LEVEL>] \
  [--taxonomy-domain <DOM>]  \
  [--json]

workflow exercise register-batch "<GLOB>" \
  --course <COURSE_CODE> \
  --cycle <CYCLE>        \
  --partial <PARTIAL_ID> \
  [--json]
```

- `--path` : absolute or workspace-relative path to the existing `.tex`
- `--type` : extends current enum with UCIMED-specific values (`SCM`, `SSU`, `SDE`)
- `--course` : institution-scoped course code (e.g. `CB0009`)
- `--cycle` : academic cycle string (e.g. `2026C1`)
- `--partial` : parcial/exam identifier (e.g. `P02`)
- `--domain` : concept-map domain slug
- `--points` : integer point value
- `register-batch` : glob-expanded multi-file registration; shares `--course/--cycle/--partial`

## Example

```bash
$ workflow exercise register \
    --path 0000EE/EnergiaFuerzas-UCIMED2026C1-P02SSUP011.tex \
    --type SSU --course CB0009 --cycle 2026C1 --partial P02 \
    --domain EnergiaFuerzasMovimientoFractura --points 2 \
    --json
[{"id": "EnergiaFuerzas-UCIMED2026C1-P02SSUP011", "registered": true, "db_row_id": 42}]

$ workflow exercise register-batch \
    "0000EE/Energia*-UCIMED-2026C1-P02SSU*.tex" \
    --course CB0009 --cycle 2026C1 --partial P02 --json
[
  {"id": "Energia...-P02SSUP011", "registered": true, "db_row_id": 42},
  {"id": "Energia...-P02SSUP012", "registered": true, "db_row_id": 43},
  ...
]
```

## Expected output shape

```json
[
  {
    "id": "<exercise-id>",
    "registered": true,
    "db_row_id": 42,
    "path": "0000EE/...",
    "course": "CB0009",
    "cycle": "2026C1",
    "partial": "P02",
    "type": "SSU"
  }
]
```

Exit codes: 0 on all files resolved and inserted without collision; 1 on any
file not found, DB collision, or unknown `--type` value.

## Acceptance test

- `test_exercise_register_existing_tex`: given a pre-written `.tex` at a
  known path, `workflow exercise register --path … --type SSU --course CB0009
  --cycle 2026C1 --partial P02 --points 2` exits 0 and the row appears in the
  `exercise` table with correct metadata.
- `test_exercise_register_type_enum_extension`: `--type SCM`, `--type SSU`,
  `--type SDE` are all accepted without error.
- `test_exercise_register_batch_glob`: a glob matching 3 test files registers
  all 3 and `--json` output is a list of length 3.
- `test_exercise_register_collision`: re-registering the same path exits 1 with
  a message containing "already registered".
- `test_exercise_register_missing_path`: nonexistent path exits 1 with a message
  containing "not found".

## Raw entries harvested

- `raw/exam-author.md#2026-04-23` — `workflow exercise create` cannot register
  an existing .tex file with UCIMED metadata
