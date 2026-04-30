---
id: 2026-04-29-exercise-list-json-filters
title: Add `--json` and `--course` filters to `workflow exercise list`
type: enhancement
source_agent: workflow-runner
opened_on: 2026-04-29
status: open
priority: P2
severity: polish
labels: [cli, exercise]
components: [workflow.exercise]
adr_refs: [ADR-0010]
related_gaps:
  - "raw/workflow-runner.md#2026-04-27-14:15"
notes: |
  src/workflow/exercise/cli.py:120 already has --type. Missing: --json, --course
  (and --cycle/--partial implied by example). Repo lookup currently goes through
  SqlExerciseRepo.find_by_filters — extend signature.
acceptance_criteria:
  - "--json emits valid JSON list (empty [] with exit 0 when no results)"
  - "--course filters by institution-scoped course code"
  - "--type values include SCM/SSU/SDE in addition to existing enum (depends on register-existing-tex request)"
  - "each JSON object contains at minimum id, file, type, course"
  - "exit 1 only on unknown --course or invalid --type"
verification:
  - "pytest tests/workflow/exercise/test_list_json.py -v"
---

# Add `--json` and `--course` filters to `workflow exercise list`

## Summary

`workflow exercise list --json` returns "No such option: --json", unlike every
sibling command in other groups that support JSON output. Querying whether an
exercise is already registered requires dropping to raw SQLite inspection.
Adding `--json` output plus `--course` and `--type` filters would make
`exercise list` consistent with the rest of the CLI and eliminate the SQLite
workaround.

## Motivation

- Reporting agent(s): workflow-runner
- Total occurrences: 1
- Severity: polish
- Blocks / slows down: confirming exercise registration status without raw SQL;
  consistent JSON-pipeline scripting across groups

## Proposed CLI

```bash
workflow exercise list [--course <CODE>] [--type <TYPE>] [--json]
```

- `--course` : filter by institution-scoped course code (e.g. `FS0211`, `CB0009`)
- `--type` : filter by exercise type (`multichoice`, `shortanswer`, `essay`,
  `numerical`, `truefalse`, `SCM`, `SSU`, `SDE`)
- `--json` : emit JSON array instead of table; empty list `[]` with exit 0
  when no results

## Example

```bash
$ workflow exercise list --course CB0009 --cycle 2026C1 --json
[
  {
    "id": "EnergiaFuerzas-UCIMED2026C1-P02SSUP011",
    "concept": "EnergiaFuerzasMovimientoFractura",
    "file": "0000EE/EnergiaFuerzas-UCIMED2026C1-P02SSUP011.tex",
    "type": "SSU",
    "course": "CB0009",
    "cycle": "2026C1",
    "partial": "P02",
    "points": 2
  }
]

$ workflow exercise list --course CB0009 --json
[]   # exit 0 when course exists but no exercises registered
```

## Expected output shape

```json
[
  {
    "id": "<exercise-id>",
    "concept": "<concept-slug>",
    "file": "<relative-path>",
    "type": "<type>",
    "course": "<course-code>",
    "cycle": "<cycle>",
    "partial": "<partial-id>",
    "points": 2,
    "status": "registered",
    "difficulty": null,
    "taxonomy_level": null
  }
]
```

Exit codes: 0 on successful query (including empty results); 1 on unknown
`--course` code or invalid `--type` value.

## Acceptance test

- `test_exercise_list_json_flag`: `workflow exercise list --json` exits 0 and
  emits valid JSON (list).
- `test_exercise_list_filter_course`: `--course CB0009` returns only rows
  matching that course.
- `test_exercise_list_filter_type`: `--type SSU` returns only SSU-type
  exercises.
- `test_exercise_list_empty_json`: when no exercises match the filter, output
  is `[]` and exit code is 0 (not an error).
- `test_exercise_list_json_keys`: each object in the list contains at minimum
  `id`, `file`, `type`, `course` keys.

## Raw entries harvested

- `raw/workflow-runner.md#2026-04-27-14:15` — `workflow exercise list` lacks
  `--json` flag; workaround required direct SQLite inspection
