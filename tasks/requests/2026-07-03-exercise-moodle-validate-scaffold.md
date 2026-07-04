---
id: 20260703-exercise-moodle-validate-scaffold
title: exercise validate-moodle (XML lint) + scaffold-moodle (weekly quiz scaffolder)
type: gap
source_agent: exam-author
opened_on: 2026-07-03

status: closed
resolution: implemented
priority: P1
severity: recurring-friction

labels:
  - cli
  - exercise
  - validation
components:
  - workflow.exercise

adr_refs: ["ADR-0012"]
related_requests: ["2026-04-29-exam-scaffold-moodle-xml"]
related_gaps:
  - raw/exam-author.md#2026-06-01
  - raw/exam-author.md#2026-06-30 14:10
  - raw/exam-author.md#2026-07-01
  - raw/exam-author.md#2026-04-27
  - raw/exam-author.md#2026-06-15
  - raw/exam-author.md#2026-06-22
duplicates: []
blocked_by: []

assignee: claude
target_release: pre-candidatura-window-2026-07
implementation:
  - src/workflow/exam/validate.py
  - src/workflow/exam/weekly.py
  - src/workflow/exam/cli.py (scaffold-xml dual-mode + validate wiring)
  - tests/workflow/exam/test_validate.py
  - tests/workflow/exam/test_scaffold_weekly.py
  - tests/fixtures/moodle/*.xml
closed_on: 2026-07-03
closed_by: "f0aa62d + 14a0f21 (write: f0aa62d + follow-up feat(exam) weekly scaffold commit)"

acceptance_criteria:
  - "`workflow exercise validate-moodle <file.xml>` checks per multichoice question: exactly one fraction=100, >=2 fraction=0, CDATA wrapping, defaultgrade/penalty/single present; exit 1 on violation with question name + rule"
  - "`--strict` additionally requires idnumber on every question and category comment presence"
  - "`workflow exercise scaffold-moodle --course --week --dc <DC.md> --kind comprension|practica` emits categories + idnumbers + TODO stub questions, no content authoring"
  - "`--category-style flat|hierarchical` with default flat; hierarchical preserved as documented opt-in"
  - "Practica-N → PC-N → Tema #(N+1) offset encoded in scaffolder, not tribal knowledge"
  - "Tests under tests/workflow/exercise/ with fixture XMLs (valid, each violation class)"
verification:
  - "uv run pytest tests/workflow/exercise -q"
  - "uv run workflow exercise validate-moodle tests/fixtures/moodle/bad-fractions.xml; echo $?  # expect 1"
  - "uv run workflow exercise scaffold-moodle --course CI0007 --week 11 --dc DC.md --kind comprension -o /tmp/out.xml && uv run workflow exercise validate-moodle /tmp/out.xml"
---

# Request: Moodle XML validate + weekly scaffold under `exercise` group

## Context

Weekly Moodle quiz production is the highest projected-volume family in the gap
log (2 files × 13 weeks × N courses; 10th weekly instance documented). Two
frictions (audit §1 #4/#11/#16):

1. **No structural validation.** `xmllint --noout` checks XML well-formedness
   only; Moodle-semantic breakage (fractions not summing, missing CDATA,
   missing defaultgrade) surfaces at import time. `src/workflow/exercise/moodle.py`
   is export-only (`exercise_to_xml`, `exercises_to_quiz_xml`) — zero validate code.
2. **No scaffolder.** Weekly Comprensión+Práctica XML pairs (UCIMED CI0007) and
   UCR lab PCs are hand-scaffolded; category-style drifted (9/11 delivered files
   are flat vs a hierarchical spec — PC11 re-authored to flat by hand), and the
   `Practica-N → PC-N → Tema #(N+1)` offset is tribal knowledge.

Decision (user, 2026-07-03): both live under the existing `exercise` group
(consistent with `export-moodle`); no new top-level `moodle`/`quiz` group.
Consolidates and closes `2026-04-29-exam-scaffold-moodle-xml.md` — one surface
for UCR PC + UCIMED weekly, not two parallel commands.

## Proposal

### Commands / API surface

```bash
workflow exercise validate-moodle <file.xml> [--strict] [--json]
workflow exercise scaffold-moodle --course <code> --week <N> --dc <DC.md> \
    --kind comprension|practica [--category-style flat|hierarchical] [-o out.xml]
```

Expected output / JSON shape (validate --json):

```json
{"file": "…", "questions": 12, "violations": [{"question": "…", "rule": "fraction-100", "detail": "…"}]}
```

### Shape of result

- validate: exit 0 iff zero violations; violations listed one-per-line (human) or array (json)
- scaffold: writes XML that passes `validate-moodle` by construction; TODO stubs
  clearly marked (`<!-- TODO: author -->` + placeholder questiontext)

## Acceptance criteria

- [x] validate rules: 1×fraction=100, ≥2×fraction=0, CDATA, defaultgrade/penalty/single (shipped as `workflow exam validate`)
- [x] --strict adds idnumber + category checks
- [x] scaffold weekly mode emits categories/idnumbers/stubs only (no content authoring)
- [x] --category-style default flat; hierarchical opt-in documented
- [x] Week/Tema offset encoded (`workflow.exam.weekly.tema_label_for_practica`)
- [x] scaffold output passes own validator (round-trip test)
- [x] Tests + fixture XMLs — actual location `tests/workflow/exam/` + `tests/fixtures/moodle/` (surface moved from `exercise` to `exam` group post-discovery, see Progress log 2026-07-03)
- [x] Docs updated: CLAUDE.md command table

## Out of scope

- Question content authoring/generation of any kind
- `build-exam --balanceo` CSV matrix (audit #17 — next sprint)
- Reposición flow (`exercise clone --variant`, `build-exam --reposicion`) — bundle C, deferred by user 2026-07-03
- Moodle import/API integration

## Evidence / glue replaced

```bash
xmllint --noout weekly.xml   # well-formedness only, no Moodle semantics
# + hand-copying last week's XML and editing categories/idnumbers (10+ instances)
```

- evidence: `src/workflow/exercise/moodle.py:95,233` (export-only); raw/exam-author.md anchors above
- frequency observed: 10th weekly instance; 3–4 UCR PC instances; 2–3 category-style reconciliation sessions

## Implementation notes

- **DISCOVERY (2026-07-03, post-audit):** `workflow exam scaffold-xml` ALREADY EXISTS
  (`src/workflow/exam/{cli,scaffold}.py`, shipped 2026-05-27, request
  `2026-04-29-exam-scaffold-moodle-xml` closed implemented — the audit's
  "consolidate" note was stale). It scaffolds one exam
  (`--course --cycle --group --label --category --out --json`). What's missing is
  exactly this request's delta: weekly DC.md-driven pair (`--week --dc --kind`),
  `--category-style flat|hierarchical`, the Tema offset, and any validator.
  [UNCLEAR → decide at implementation]: recommended surface is to EXTEND
  `exam scaffold-xml` + add `exam validate` (keeps one scaffold engine), even
  though the user picked "under exercise" before this discovery surfaced.
- Reuse XML building blocks from `moodle.py` export path and `exam/scaffold.py` for scaffold stubs; validator parses with stdlib `xml.etree` (no new dep).
- DC.md parsing: keep minimal — headings → categories; do not build a general DC parser (that's R4 territory).
- If window closes early: ship validate-moodle alone (droppable-scaffold decision recorded in roadmap).

## Progress log

- 2026-07-03 — opened by claude; consolidates 2026-04-29-exam-scaffold-moodle-xml + audit slugs #4/#11/#16; surface decision (exercise group) by user
- 2026-07-03 — **Surface decision revised (post-discovery):** final surface is `workflow exam validate` and
  `workflow exam scaffold-xml --week/--dc/--kind/--category-style`, NOT `exercise validate-moodle`/
  `exercise scaffold-moodle` as originally scoped. `exam scaffold-xml` already existed (2026-05-27); extending
  it in place — rather than adding a second, parallel `exercise` surface — keeps one scaffold engine.
  Implementation summary:
  - **`exam validate`** (`src/workflow/exam/validate.py`, Phase 1, commit `f0aa62d`): per-multichoice-question
    rules — exactly one `fraction=100`, ≥2 `fraction=0`, CDATA wrapping, `defaultgrade`/`penalty`/`single`
    present; `--strict` adds `idnumber` + category-question presence; a loudness guard fails the whole file if
    the raw CDATA scan and `xml.etree` question count disagree (never silently under-checks); exit 1 on any
    violation; `--json` emits `{file, questions, violations[]}`. 19 tests + 8 fixture XMLs under
    `tests/fixtures/moodle/`.
  - **`exam scaffold-xml` weekly mode** (`src/workflow/exam/weekly.py` + `cli.py` dual-mode dispatch, Phase 2,
    uncommitted at doc-close time, landing as a follow-up `feat(exam)` commit): `--week/--dc/--kind` reads a
    DC.md's `##` headings as categories (`parse_dc_headings`); builds `WWCCNN` idnumbers with a 1..99 guard per
    field (`build_idnumber`); encodes `Practica-N → PC-N → Tema #(N+1)` via `tema_label_for_practica`; supports
    `--category-style flat` (default) or `hierarchical`; guards against a `]]>` CDATA terminator inside a
    heading; includes a round-trip test asserting scaffold output passes `exam validate --strict` with zero
    violations. Mixing legacy (`--cycle/--group/--label/--category/--blocks`) and weekly options is a
    `click.UsageError`. 42 new tests.
  - 43 new tests total across both phases; full suite green (2336 passed) per `verification` commands run
    against the `exam` surface equivalents of the ones listed below.
  - See CLAUDE.md Key Patterns bullet for `src/workflow/exam/` (added 2026-07-03) for the user-facing contract.

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [x] All acceptance criteria checked
- [x] `verification` commands pass on master (against the `exam` surface equivalents — see Progress log)
- [x] `implementation` frontmatter list filled
- [x] `closed_by` references commit/PR/ADR
- [ ] `2026-04-29-exam-scaffold-moodle-xml.md` closed as superseded — **N/A by design**: that request was
  extended, not superseded, and remains `status: completed` / `resolution: implemented`. A one-line
  cross-link was added to its Progress log instead (see that file).
- [ ] Related gap log entries cross-linked back to this request id — out of scope for this doc-closure pass
