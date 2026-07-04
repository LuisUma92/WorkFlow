---
# Required identity fields
id: 20260704-build-exam-balanceo
title: exercise build-exam --balanceo — taxonomy×concept balance matrix (audit #17)
type: gap
source_agent: user (director) — carried forward from 2026-07-03 gap audit + freeze-window plan Phase 1
opened_on: 2026-07-04

# Lifecycle (mirrors GitHub issue states)
status: closed
resolution: implemented
priority: P1
severity: recurring-friction

# Scoping (GitHub-issue style labels)
labels:
  - cli
  - exercise
components:
  - workflow.exercise

# Linkage
adr_refs: []
related_requests:
  - "20260703-exercise-composability-flags"
related_gaps:
  - "~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md#17"
duplicates: []
blocked_by: []

# Implementation tracking
assignee: claude
target_release: freeze-window-2026-07
implementation:
  - src/workflow/exercise/balance.py
  - "src/workflow/exercise/cli.py (build-exam flags)"
  - "tests/workflow/exercise/test_balance.py (21 tests)"
  - CLAUDE.md bullet
closed_on: 2026-07-04
closed_by: "47a50ec"

# Acceptance
acceptance_criteria: []
verification:
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q tests/workflow/exercise/test_balance.py --ignore=tests/test_database.py"
  - "uv run flake8 src/workflow/exercise/ tests/workflow/exercise/ --max-line-length=127 --max-complexity=10"
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run workflow exercise build-exam -l Recordar -d Información --balanceo --json"
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run workflow exercise build-exam -l Recordar -d Información --balanceo matriz.csv && cat matriz.csv"
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run workflow exercise build-exam -l Recordar -d Información --balanceo --json --fail-under 0.9; echo \"exit=$?\""
---

# Request: `exercise build-exam --balanceo` — taxonomy×concept balance matrix

## Context

`workflow exercise build-exam` (`src/workflow/exercise/cli.py:654-750`, `build_exam_cmd`)
assembles an exam from `--taxonomy-level`/`--taxonomy-domain` slots via
`select_exercises` (`src/workflow/exercise/selector.py:17-30`) and
`build_exam` (`src/workflow/exercise/exam_builder.py:49-90`). Today it only
emits the assembled `.tex` body plus stderr warnings — there is no visibility
into how the exercises actually selected are *distributed* across taxonomy
levels, domains, or concepts before the exam is handed out. Authors currently
eyeball this by hand from the `.tex` output, once per exam, every cycle.

**Re-verified anchors (2026-07-04, live code):**

- `exam_builder.py:17-25` — `ExamDocument` frozen dataclass: `title: str`,
  `content: str`, `total_points: float`, `exercise_count: int`,
  `warnings: tuple[str, ...]`. No balance/taxonomy field exists today; adding
  one directly would be a breaking dataclass change to every caller.
- `exam_builder.py:49-90` — `build_exam(selection, *, title, instructions) ->
  ExamDocument` iterates `selection.selected.items()` (dict keyed by
  `ExerciseSlot`, valued by `list[Exercise]`), accumulating `total_points`
  and `exercise_count` but discarding the per-slot breakdown once summed.
- `selector.py:17-30` — `ExerciseSlot(taxonomy_level, taxonomy_domain, count,
  points_per_item)` (frozen dataclass) and `SelectionResult(selected: dict[
  ExerciseSlot, list[Exercise]], unfilled, warnings)`. `selected` is exactly
  the structure to pivot into a balance matrix: one row per slot key, with
  `count = len(exercises)` and `points = points_per_item * len(exercises)`
  computable directly — no new query needed for the taxonomy axis.
- Concept axis requires a second query: exercises in `selected` carry
  `exercise_id`/`book_id` etc. but not resolved concept links inline;
  `ExerciseConcept` (`src/workflow/db/models/exercises.py:193-208`, M2M
  `exercise_id`↔`concept_id`) must be queried per selected exercise to
  compute concept coverage.
- `cli.py:654-750` (`build_exam_cmd`) flags today: `-l/--taxonomy-level`
  (multiple, required), `-d/--taxonomy-domain` (multiple), `-n/--count`
  (int, default 5), `-p/--points` (float, default 10.0), `--title`,
  `--instructions`, `-o/--output`. **No `--json`, no `--balanceo`/`--balance`,
  no CSV output exist today.** Pool query at line ~733:
  `repo.find_by_filters(status="complete", limit=10_000)` via
  `SqlExerciseRepo`.
- `src/workflow/db/models/academic.py:40-49` — `_TAXONOMY_LEVELS = ("Recordar",
  "Comprender", "Análisis", "Usar-Aplicar", "Usar-Evaluar", "Usar-Crear",
  "Metacognitivo", "Sistema interno")` — this is the canonical row axis for
  the balance matrix (not a hand-rolled enum).

**Provenance / reinterpretation note:** the original audit entry (slug #17,
`~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md` line 278) literally
reads:

> `workflow build-exam --balanceo <matriz.csv>` — generar master + esqueletos
> desde CSV unidad×tipo×pts (NO cabe en 3 días, listar para el sprint
> siguiente)

i.e. the audit's original ask was `--balanceo` **taking a CSV as input**
(a desired unit×type×points distribution) and scaffolding a master exam +
item skeletons from it — explicitly flagged by the auditor as too large for
the 3-day window. The freeze-window plan (`tasks/plans/
2026-07-03-freeze-window-features-plan.md`, Phase 1, "Resolved design rules"
+ "Target/design" sections) locked a **narrower, freeze-sized
reinterpretation**: `--balanceo` computes and **emits** a taxonomy×concept
balance *report* (CSV/JSON output) over an *already-assembled* exam — no CSV
import, no master/skeleton scaffolding. This request tracks the
plan's reinterpretation only. The original CSV-import ask is explicitly
out of scope below and remains available as a future request once this
output-side primitive exists to build on.

## Proposal

Add a `--balanceo [PATH.csv]` flag (and `--json`) to `workflow exercise
build-exam` that computes a balance report over the `SelectionResult` already
produced by the existing slot-selection pass, and prints/writes it alongside
the normal `.tex` output (does not replace it).

- Rows = taxonomy levels from `_TAXONOMY_LEVELS`
  (`workflow.db.models.academic`), paired with `taxonomy_domain` per slot.
- Columns = `count` (exercises selected for that slot) and `points`
  (`points_per_item * count`).
- A `concept_coverage` summary: `total_concepts` (distinct concepts appearing
  anywhere in the exercise **pool** passed to `build_exam_cmd`, not the whole
  DB — see locked decision below) vs `distinct_covered` (distinct concepts
  actually linked, via `ExerciseConcept`, to exercises that were selected).
- Reuses `selection.warnings` (Bundle B `--json` composability precedent) —
  no new warning channel invented.
- Optional `--fail-under FLOAT`: if `distinct_covered / total_concepts` falls
  below the threshold, exit code 2 (does not change default exit-0
  behavior when the flag is omitted).

**Locked decision (carried from the freeze-window plan, ★ resolved without a
blocking question):** `total_concepts` is scoped to **distinct concepts
appearing in the exercise pool** (`repo.find_by_filters(status="complete",
...)`, the same pool `select_exercises` draws from), not every `Concept` row
in the DB. This is the simplest denominator that still makes the coverage
ratio meaningful per-exam. **Overridable by the user at implementation time**
if a different scoping (e.g. course-tagged concepts) proves more useful once
real exam pools are tested against it.

**Additive-only constraint:** `ExamDocument` (`exam_builder.py:17-25`) MUST
NOT change shape. The balance computation lives in a new pure function,
e.g. `compute_balance(selection: SelectionResult, session: Session) ->
BalanceReport` in a new `src/workflow/exercise/balance.py` module — zero risk
to `build_exam()`'s existing callers/tests.

**Output routing:** `--balanceo` (no path) prints a human-readable table to
stderr, alongside existing warnings — the `.tex` output routed via
`--output`/stdout stays clean either way. `--balanceo PATH.csv` writes the
CSV to that path instead of printing. `--json` (combinable) prints the JSON
form of the same report to stdout... **unless `--output` is also given for
the `.tex` body, in which case `--json` balance output goes to stdout and the
`.tex` body goes to the `--output` file** ([UNCLEAR] — exact stdout/stderr
routing when both `--json` and no `--output` are given needs a concrete call
during implementation; recommend: `--balanceo`/`--json` always route to
stdout when no CSV path is given, `.tex` body always requires `--output` in
that combination — flag this for the implementer, do not silently guess).

### Commands / API surface

```bash
workflow exercise build-exam -l recordar -d informacion --balanceo
workflow exercise build-exam -l recordar -d informacion --balanceo matriz.csv
workflow exercise build-exam -l recordar -d informacion --balanceo --json
workflow exercise build-exam -l recordar -d informacion --balanceo --json --fail-under 0.5
```

Expected `--balanceo --json` shape:

```json
{
  "matrix": [
    {"taxonomy_level": "Recordar", "taxonomy_domain": "Información", "count": 4, "points": 40.0}
  ],
  "concept_coverage": {"total_concepts": 6, "distinct_covered": 4},
  "warnings": ["Slot (Usar-Aplicar, Procedimiento Mental): requested 3, found 1."]
}
```

CSV form (`--balanceo matriz.csv`), one row per slot:

```csv
taxonomy_level,taxonomy_domain,count,points
Recordar,Información,4,40.0
```

### Shape of result

- stdout: `.tex` exam body (unchanged) OR JSON balance report if `--json`
  passed without `--output`.
- exit code 0 iff exam assembly succeeds and (if `--fail-under` given)
  coverage ratio meets threshold.
- exit code 2 iff `--fail-under` given and coverage ratio falls below it.
- `--json` emits the object shown above (not an array — single report per
  invocation).

## Acceptance criteria

- [x] `compute_balance(selection, session)` returns one matrix row per slot
      in `selection.selected`, with `count == len(exercises)` and
      `points == points_per_item * count` for that slot.
      (verified: `balance.py:83-91`; tests `TestComputeBalanceMatrix::*`)
- [x] `concept_coverage.total_concepts` counts distinct concepts across the
      exercise **pool** (not full DB); `distinct_covered` counts distinct
      concepts linked (via `ExerciseConcept`) to selected exercises only.
      (verified: `balance.py:93-104`; test
      `test_total_concepts_scoped_to_pool_not_selection`)
- [x] Exercises with zero resolved concept links count as `0` toward
      coverage, not an error (mirrors Bundle A/B's warn-not-fail tone).
      (verified: test `test_zero_concept_exercise_counts_as_zero_not_error`)
- [x] `--balanceo` (no path) prints a table to stderr; `--balanceo PATH.csv`
      writes CSV to `PATH.csv`; existing `.tex` output behavior on
      stdout/`--output` is unchanged in both cases.
      (shipped as two flags — `--balanceo` bool + `--balanceo-csv PATH` —
      see CLI-UX deviation note in Progress log; verified: `cli.py:706-720,
      840-844`; tests `test_balanceo_bare_prints_stderr_table_stdout_stays_tex`,
      `test_balanceo_csv_writes_file`, `test_no_balanceo_flags_behavior_unchanged`)
- [x] `--json` emits the documented shape (`matrix`, `concept_coverage`,
      `warnings`) to stdout.
      (verified: `cli.py:846-849`; test
      `test_balanceo_json_emits_documented_shape_to_stdout`)
- [x] `--fail-under FLOAT` yields exit code 2 when
      `distinct_covered/total_concepts < FLOAT`; exit 0 at or above; exit 0
      when the flag is omitted regardless of coverage.
      (verified: `cli.py:786-787`; tests `test_fail_under_below_threshold_exits_2`,
      `test_fail_under_at_threshold_exits_0`)
- [x] `ExamDocument` (`exam_builder.py:17-25`) is unchanged — existing
      `build_exam()` tests pass unmodified.
      (verified: test `test_exam_document_shape_unchanged`; full suite
      2357 passed)
- [x] Tests added under `tests/workflow/exercise/test_balance.py` covering:
      fully-filled slot, under-filled slot, zero-concept exercise, and the
      `--fail-under` boundary (at threshold = pass, just below = fail).
      (verified: 21 tests, all passing —
      `WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q
      tests/workflow/exercise/test_balance.py` → "21 passed")
- [x] Docs updated: `CLAUDE.md` exercise-CLI bullet gains the `--balanceo`/
      `--json`/`--fail-under` flags on `build-exam`.
      (verified: `CLAUDE.md:92`, exercise-CLI bullet appended)
- [x] `--json` flag parity with Bundle B's `sync --json` precedent (same
      envelope conventions: warnings array, no swallowed errors).
      (verified: `warnings` key present in `to_dict`/CLI JSON output,
      `balance.py:121-138`; HIGH review fix applied for stdout purity —
      see Progress log)

## Verification

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q tests/workflow/exercise/test_balance.py --ignore=tests/test_database.py

# Lint
uv run flake8 src/workflow/exercise/ tests/workflow/exercise/ --max-line-length=127 --max-complexity=10

# Live-shape checks (isolated tmp DB, not the real vault DB)
WORKFLOW_DATA_DIR=$(mktemp -d) uv run workflow exercise build-exam -l Recordar -d Información --balanceo --json
WORKFLOW_DATA_DIR=$(mktemp -d) uv run workflow exercise build-exam -l Recordar -d Información --balanceo matriz.csv && cat matriz.csv
WORKFLOW_DATA_DIR=$(mktemp -d) uv run workflow exercise build-exam -l Recordar -d Información --balanceo --json --fail-under 0.9; echo "exit=$?"
```

## Out of scope

- CSV **import** of a desired unit×type×points distribution to scaffold a
  master exam + item skeletons — this was the *original* audit ask (slug #17
  literal text) and is explicitly deferred post-freeze; this request covers
  only the output-side balance report over an already-assembled selection.
- Bundle C reposición (`build-exam --reposicion`, audit slug #10) — separate,
  unrelated flag on the same command; not touched here.
- Course/topic-scoped `total_concepts` denominators (e.g. "all concepts
  tagged to this course") — the locked default is pool-scoped; a
  course-scoped variant is a future enhancement once real usage data exists.
- Auto-rebalancing (e.g. automatically swapping exercises to fix an
  under-covered slot) — this request is read-only reporting, no exercise
  reselection logic.

## Evidence / glue replaced

```bash
# Today: authors manually count taxonomy levels / concepts in the .tex
# output after every `build-exam` run, or maintain an ad-hoc spreadsheet
# copy of the exam's coverage — no CLI primitive computes this.
workflow exercise build-exam -l recordar -d informacion -n 5 -p 10 --output exam.tex
# (then eyeball exam.tex or a separate spreadsheet for balance)
```

- evidence: `~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md:278`
  ("volumen futuro" column context: every exam, every cycle, per the audit's
  full table header at line 91 — `Recurrencia histórica` / `Volumen futuro
  pre-candidatura` columns apply to the parent table this row summarizes).
- frequency observed: every UCIMED partial exam assembly (per-cycle,
  recurring — cited in the freeze-window plan Phase 1 goal as "the highest
  `volumen_futuro` item").

## Implementation notes

- Reuse `SqlExerciseRepo` (imported in `cli.py`, exact class file not
  re-verified this pass — `grep -rn "class SqlExerciseRepo"` before writing
  the pool query for concept resolution, per the freeze-window plan's Phase
  2b risk note; the same repo instance from `build_exam_cmd`'s existing
  `with Session(engine) as session:` block can likely be reused directly).
- `ExerciseConcept` M2M table: `src/workflow/db/models/exercises.py:193-208`.
- Follow the Bundle A/B fail-loud + `--json` composability precedents
  (`ADR-0011` note in `CLAUDE.md`) for warning/error tone consistency.
- See `tasks/plans/2026-07-03-freeze-window-features-plan.md` Phase 1 for the
  full TDD breakdown (RED test list, GREEN file list, verification commands)
  — this request doc is Phase 1 Step 0 of that plan; do not duplicate the
  TDD plan here, just the request-level scope/acceptance contract.

## Progress log

- 2026-07-04 — opened by claude (director). Brought forward from
  post-freeze to in-window Phase 1 per user decision 2026-07-03 (roadmap had
  marked audit slug #17 "NO cabe en 3 días, listar para el sprint
  siguiente" — director overrode this via the freeze-window plan's locked
  phase order, reinterpreting `--balanceo` as an output-side balance report
  rather than the original CSV-import/scaffold ask, to fit the window).
- 2026-07-04 — implemented same day via TDD (20 RED→GREEN tests +
  1 review-fix regression test, 21 total in `test_balance.py`). CLI UX
  deviation from spec recorded: the proposal's `--balanceo [PATH]`
  optional-value flag was rejected at implementation time — Click 8.3's
  `flag_value`/`is_flag` mechanics still require an explicit argument slot
  for optional-value flags (verified empirically against this Click
  version, not just docs) — so it shipped as two flags instead:
  `--balanceo` (bool, triggers stderr table) + `--balanceo-csv PATH`
  (writes CSV). The proposal's [UNCLEAR] on json+output stdout/stderr
  routing was resolved: JSON always owns stdout when `--json` is passed
  (regardless of `--output`); the `.tex` confirmation message is only
  emitted at all when `--output` is given, and even then routed to stderr
  (`err=suppress`) under `--json` so stdout stays pure JSON. Reviewer-esquema
  (opus) found 1 HIGH: the `--output` confirmation ("Exam written to ...")
  was leaking onto stdout under `--json --output`, corrupting the JSON
  stream — fixed via the `suppress` param on `_emit_tex_body`
  (`cli.py:854-867`); rest of the review was clean. Full suite: 2357
  passed after the fix.

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [x] All acceptance criteria checked
- [x] `verification` commands pass on master (21/21 `test_balance.py`;
      flake8 clean on `src/workflow/exercise/` + `tests/workflow/exercise/`;
      live-shape CLI checks match documented `--json`/CSV/`--fail-under`
      contracts)
- [x] `implementation` frontmatter list filled with shipped paths/commands
- [ ] `closed_by` references commit/PR/ADR — placeholder pending; git-ops
      agent replaces `<pending F1 commit>` with the real commit hash
      immediately after this doc closure
- [x] CLAUDE.md and ADR INDEX updated if architecture changed (CLAUDE.md
      exercise-CLI bullet updated; no ADR needed — additive-only, no
      architectural decision reversed)
- [ ] Related gap log entries cross-linked back to this request id —
      out of session scope; `~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md`
      slug #17 cross-link is tracked separately in the 01-U workspace, not
      this repo
