---
id: 2026-04-29-exam-scaffold-moodle-xml
title: Add `workflow exam scaffold-xml` to generate Moodle quiz skeletons
type: feature
source_agent: exam-author
opened_on: 2026-04-29
status: proposed
priority: P1
severity: recurring-friction
labels: [cli, exercise]
components: [workflow.exercise, workflow.latex]
adr_refs: [ADR-0010, ADR-0012]
related_gaps:
  - "raw/exam-author.md#2026-04-27"
acceptance_criteria:
  - "workflow exam scaffold-xml --course --cycle --group --label --category --blocks 'Name:N,...' [--question-prefix] [--penalty F] [--grade N] --out PATH writes valid Moodle XML"
  - "output passes xmllint --noout"
  - "block boundaries preceded by XML comment with block name"
  - "--penalty/--grade reflected in every <question> block"
  - "all <questiontext>/<answer>/<feedback> contain CDATA[TODO] placeholders"
  - "distinct distractor labels (Answer 1, Answer 2, ...) so duplicate-paste bug cannot recur"
  - "--json emits {path, questions, blocks, valid_xml}"
  - "exit 1 on invalid --blocks spec or unwritable path"
verification:
  - "pytest tests/workflow/exercise/test_scaffold_xml.py -v"
  - "xmllint --noout <generated path>"
---

# Add `workflow exam scaffold-xml` to generate Moodle quiz skeletons

## Summary

Every Moodle XML quiz (PC03, PC04, …) is hand-authored from scratch. A
20-question multichoice quiz requires ~520 lines of repetitive boilerplate:
correct `<quiz>` header, one category question, per-block separator comments,
and 20 `<question type="multichoice">` blocks each with `<defaultgrade>`,
`<penalty>`, `<single>`, `<shuffleanswers>`, `<answernumbering>`,
`<generalfeedback>`, and per-answer `<feedback>` stubs. Manual authoring
introduces consistency bugs (duplicate distractors caught in PC04 only by
chance).

## Motivation

- Reporting agent(s): exam-author
- Total occurrences: 2 (PC03 + PC04 for UCR FS0211, same pattern both times)
- Severity: recurring-friction
- Blocks / slows down: each new PC requires 30–60 min of XML scaffolding before
  any pedagogical content can be written; format bugs waste review time

## Proposed CLI

```bash
workflow exam scaffold-xml \
  --course <COURSE_CODE>     \
  --cycle <CYCLE>            \
  --group <GROUP>            \
  --label <LABEL>            \
  --category "<CATEGORY_PATH>" \
  --blocks "<BLOCK_SPEC>"    \
  [--question-prefix "<STR>"] \
  [--penalty <FLOAT>]        \
  [--grade <INT>]            \
  --out <OUTPUT_PATH>
```

- `--blocks` : comma-separated `Name:count` pairs (e.g.
  `"Recordar:4,Comprender:4,Analizar-info:4,Analizar-proc:4,Usar-Aplicar:4"`)
- `--penalty` : per-wrong-answer penalty (default `0.25`)
- `--grade` : default grade per question (default `1`)
- Output: valid Moodle XML with `<![CDATA[TODO]]>` placeholders in all
  question/answer/feedback text; passes `xmllint --noout`.

## Example

```bash
$ workflow exam scaffold-xml \
    --course FS0211 --cycle 2026C1 --group 001 \
    --label "PC04" \
    --category "Tema #06 Leyes del movimiento II" \
    --blocks "Recordar:4,Comprender:4,Analizar-info:4,Analizar-proc:4,Usar-Aplicar:4" \
    --question-prefix "Leyes del Movimiento II" \
    --penalty 0.25 --grade 1 \
    --out eval/pruebas_cortas/2026C1-G001-PC04.xml
Wrote 21 questions (1 category + 20 multichoice) to
eval/pruebas_cortas/2026C1-G001-PC04.xml
```

## Expected output shape

The generated file is valid Moodle XML. CLI stdout on success:

```
Wrote <N> questions (1 category + <N-1> multichoice) to <path>
```

With `--json`:

```json
{
  "path": "eval/pruebas_cortas/2026C1-G001-PC04.xml",
  "questions": 21,
  "blocks": [
    {"name": "Recordar", "count": 4},
    {"name": "Comprender", "count": 4}
  ],
  "valid_xml": true
}
```

Exit codes: 0 on valid file written; 1 on invalid `--blocks` spec, missing
required flags, or output path not writable.

## Acceptance test

- `test_scaffold_xml_basic`: given a 5-block spec summing to 20 questions,
  the output file has exactly 21 `<question>` elements (1 category + 20) and
  passes `xmllint --noout`.
- `test_scaffold_xml_block_comments`: each block boundary is preceded by an
  XML comment containing the block name.
- `test_scaffold_xml_penalty_grade`: `--penalty 0.33 --grade 2` are reflected
  in every `<question>` block's attributes.
- `test_scaffold_xml_cdata_placeholders`: all `<questiontext>`, `<answer>`,
  and `<feedback>` nodes contain `CDATA[TODO]` (not empty).
- `test_scaffold_xml_no_duplicate_distractors`: the skeleton emits distinct
  placeholder labels (`Answer 1`, `Answer 2`, …) so human authors cannot
  accidentally copy-paste the same distractor.

## Raw entries harvested

- `raw/exam-author.md#2026-04-27` — no CLI to scaffold Moodle XML quiz from
  spec (UCR PC authoring fully manual); PC03 + PC04 both hand-authored
