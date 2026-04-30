---
id: 2026-04-29-course-add-practice-quiz
title: Add `workflow course add-practice` to register lab practices and quizzes
type: feature
source_agent: workflow-runner
opened_on: 2026-04-29
status: open
priority: P1
severity: blocker
labels: [cli, db]
components: [workflow.evaluation, workflow.db, itep]
adr_refs: [ADR-0016, ITEP-0002]
related_requests: [2026-04-29-evaluations-schema-migration]
related_gaps:
  - "raw/workflow-runner.md#2026-04-27-14:22"
acceptance_criteria:
  - "workflow course add-practice <CODE> --name --week --type [--serial] [--file] inserts row in course_evaluation"
  - "workflow course practices <CODE> [--json] lists registered practices/quizzes ordered by type, serial"
  - "auto-increment serial when --serial omitted"
  - "exit 1 on serial collision with message 'already registered'"
  - "exit 1 on unknown course code with 'course not found'"
  - "tests under tests/workflow/evaluation/ for register, list, collision, auto-serial, unknown-course"
verification:
  - "pytest tests/workflow/evaluation/test_course_practices.py -v"
---

# Add `workflow course add-practice` to register lab practices and quizzes

## Summary

The `course_evaluation` and `evaluation_template` tables exist in the DB schema
but have no user-facing CLI. There is no command to register a lab practice
(P00N) or short quiz (PCnn) to a course, nor to query which assessments are
already registered. Authoring the next PC or lab practice requires hand-editing
the database or guessing the naming convention, since no CLI exposes the
registration protocol.

## Motivation

- Reporting agent(s): workflow-runner
- Total occurrences: 1 (blocks PC04 authoring for UCR-FS0211 2026C1)
- Severity: blocker
- Blocks / slows down: determining the correct serial number for the next
  practice/quiz; registering assessment metadata before authoring begins;
  any downstream `workflow evaluations list` query

## Proposed CLI

```bash
workflow course add-practice <COURSE_CODE> \
  --name "<TITLE>"         \
  --week <N>               \
  --type <practice|quiz>   \
  [--serial <N>]           \
  [--file <PATH>]          \
  [--json]

workflow course practices <COURSE_CODE> [--json]
```

- `add-practice` : registers one assessment (lab practice or quiz) to the
  named course.
- `--serial` : explicit serial number (e.g. `4` for PC04, `5` for P005);
  auto-increments if omitted.
- `--file` : optional path to the `.xml` / `.tex` source file.
- `practices` : lists all registered practices/quizzes for the course,
  ordered by type then serial.

## Example

```bash
$ workflow course add-practice FS0211 \
    --name "Leyes del Movimiento II" \
    --week 6 --type quiz --serial 4 \
    --file eval/pruebas_cortas/2026C1-G001-PC04.xml \
    --json
{"id": 7, "course": "FS0211", "type": "quiz", "serial": 4,
 "name": "Leyes del Movimiento II", "week": 6,
 "file": "eval/pruebas_cortas/2026C1-G001-PC04.xml"}

$ workflow course practices FS0211 --json
[
  {"serial": 1, "type": "quiz", "name": "Cinemática I", "week": 2, "file": "...PC01.xml"},
  {"serial": 4, "type": "quiz", "name": "Leyes del Movimiento II", "week": 6, "file": "...PC04.xml"}
]
```

## Expected output shape

```json
// add-practice --json (single registration)
{
  "id": 7,
  "course": "FS0211",
  "type": "quiz",
  "serial": 4,
  "name": "Leyes del Movimiento II",
  "week": 6,
  "file": "eval/pruebas_cortas/2026C1-G001-PC04.xml"
}

// practices --json (list)
[
  {"serial": 1, "type": "quiz", "name": "...", "week": 2, "file": "..."},
  ...
]
```

Exit codes: 0 on success; 1 on unknown course code, serial collision (with
message "serial 4 already registered for FS0211 quiz — use --serial to
override"), or missing required flags.

## Acceptance test

- `test_course_add_practice_registers_quiz`: `workflow course add-practice
  FS0211 --name "…" --week 6 --type quiz --serial 4` exits 0 and the row
  appears in `course_evaluation`.
- `test_course_practices_lists_all`: after registering 2 entries, `workflow
  course practices FS0211 --json` returns a list of length 2 with correct
  fields.
- `test_course_add_practice_serial_collision`: registering serial 4 twice
  exits 1 with message containing "already registered".
- `test_course_add_practice_auto_serial`: omitting `--serial` assigns the
  next available integer.
- `test_course_add_practice_unknown_course`: unknown course code exits 1 with
  "course not found".

## Raw entries harvested

- `raw/workflow-runner.md#2026-04-27-14:22` — no CLI command to register
  practices or quizzes by course
