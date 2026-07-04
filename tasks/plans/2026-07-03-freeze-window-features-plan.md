# Implementation plan — Freeze-window features (post-Bundle A/B/D)

Request: n/a (multi-feature roadmap plan; Phase 1 spawns its own request doc)
ADR: n/a (Phase 0a is ADR-INDEX hygiene only; no new ADR needed for Phases 1–3)
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.
Model routing: opus=review, sonnet=TDD, haiku=git-ops.

---

## Verified anchors (confirmed in code)

- `src/workflow/graph/cli.py:119-238` — `_expand_by_depth`, `_parse_cluster_name`,
  `_filter_by_cluster`, `_filter_by_tags` (plus `_build_full_graph:108`) all live
  in the CLI module today, under a `# ── Graph filter helpers (Wave 4) ──` banner
  (line 105). Pure functions, no Click decorators, no `ctx` dependency — safe to
  move verbatim.
- `tests/workflow/test_graph_export.py:17` imports `_expand_by_depth` directly
  from `workflow.graph.cli`; `TestExpandByDepth` (103), `TestClusterFilter` (162),
  `TestTagFlags` (370) exercise the four helpers. Moving the functions requires
  updating this import line only if the refactor re-exports them from
  `graph.cli` (recommended: re-export for zero test churn).
- `docs/ADR/INDEX.md:82` — ITEP-0013 status cell reads `Accepted` already
  (not `Proposed`) — **[UNCLEAR]/correction**: roadmap says "ITEP-0013
  Proposed→Accepted" but live INDEX.md already shows `Accepted`. Only
  ITEP-0014 (`Proposed`, line 83) and ITEP-0015 (`Proposed`, line 84) need
  action, and both rows **already exist** in the table (`Knowledge Layer:
  Zettelkasten & Notes`, lines 74-84). So Phase 0a reduces to: verify the
  ITEP-0013 row is correct as-is (it is) and decide whether ITEP-0014/0015
  should flip to `Accepted` too, or stay `Proposed` pending their own gates
  (ITEP-0014 explicitly "parked by own ADR gate" per roadmap backlog). **Do
  not flip 0014/0015 status** — only confirm the rows exist and are
  cross-linked correctly. This phase may be closeable as a no-op once verified.
- `src/workflow/exercise/exam_builder.py:49-90` — `build_exam(selection, *,
  title, instructions) -> ExamDocument`. `ExamDocument` (17-25): `title`,
  `content`, `total_points: float`, `exercise_count: int`,
  `warnings: tuple[str, ...]`. No balance/taxonomy breakdown field today.
- `src/workflow/exercise/selector.py:17-30` — `ExerciseSlot(taxonomy_level,
  taxonomy_domain, count, points_per_item)` frozen dataclass;
  `SelectionResult(selected: dict[ExerciseSlot, list[Exercise]], unfilled,
  warnings)`. `selected` is the exact structure a balance-matrix pass over —
  keyed by slot (taxonomy level × domain), valued by the chosen `Exercise`
  rows, each of which carries `taxonomy_level`/`taxonomy_domain` (redundant
  with slot) but **not** concept/topic — concept counts require a second
  query via `ExerciseConcept` (`src/workflow/db/models/exercises.py:193-208`,
  M2M `exercise_id`↔`concept_id`).
- `src/workflow/exercise/cli.py:654-750` — `build_exam_cmd`. Flags today:
  `-l/--taxonomy-level` (multiple, required), `-d/--taxonomy-domain`
  (multiple), `-n/--count` (int, default 5), `-p/--points` (float, default
  10.0), `--title`, `--instructions`, `-o/--output`. No `--json`, no
  `--balanceo`/`--balance` flag, no CSV output today. Pool query at line
  ~729: `repo.find_by_filters(status="complete", limit=10_000)` via
  `SqlExerciseRepo`.
- `src/workflow/exercise/cli.py:246-310` (`list_exercises`) — existing
  `--concept` flag (262) resolves via `resolve_concepts` (strict=True) from
  `workflow.concept.service`; reuse this pattern for `--chapter`.
- `src/workflow/db/models/exercises.py:44-120` — `Exercise` has **no**
  `chapter`/`chapter_number` column and no `content_id` (removed per
  CLAUDE.md M2M note). It has `book_id: FK → bib_entry.id` (line ~96-101).
  Chapter data lives on `BibContent` (`src/workflow/db/models/bibliography.py:
  366-383`): `bib_entry_id`, `content_id` (composite PK), `chapter_number:
  int`, `section_number: int`, `first_page`, `last_page`,
  `first_exercise: int | None`, `last_exercise: int | None`. **A `--chapter`
  filter on `exercise list` therefore requires a join**: `Exercise.book_id ==
  BibContent.bib_entry_id` AND the exercise's numeric suffix (parsed from
  `exercise_id`, e.g. `phys-gauss-001` → `1`) falls within
  `[first_exercise, last_exercise]` of the matching `BibContent` row, then
  filter by `chapter_number`. **[UNCLEAR]**: no existing helper parses the
  numeric suffix from `exercise_id` — grepped `parser.py`/`service.py`, no
  hits. This makes `--chapter` **M-size**, not the S the roadmap assumed;
  flagged below in Phase 2.
- `share/latex/sty/SetCommands.sty:24` — `\newcommand{\exa}[2][]{...}` (optional
  area arg, required id arg) — the macro `#5 \exa lint-units` targets.
  `share/latex/sty/SetUnits.sty` exists (confirmed) and declares custom SI
  units (`\barn`, `\ace`, `\vel`, `\denV`, etc., lines 17-40) via
  `\DeclareSIUnit`. **[UNCLEAR]**: no existing Python parser reads
  `SetUnits.sty` to build a whitelist of declared unit macros — this must be
  written from scratch (regex over `\DeclareSIUnit\<name>{...}` lines); no
  reusable brace-counting extractor for `.sty` files exists in
  `workflow.latex` today (`braces.py`/`comments.py` target exercise `.tex`
  frontmatter, not `.sty` macro tables).
- `src/workflow/evaluation/cli.py:360-403` — `course add-practice` **already
  exists and is shipped**: `@course.command(name="add-practice")`, args
  `COURSE_CODE --name --week --type {practice,quiz} [--serial] [--file]
  [--json]`, calls `add_practice()` (`src/workflow/evaluation/service.py:184`).
  **This directly contradicts the roadmap's audit slug #14** ("post-window P2
  — surface decision needed; `course --help` unverified"). The surface
  decision is moot — the command is live. Phase 3 is therefore corrected
  below from "implement" to "verify/extend only."
- `tasks/requests/2026-05-03-note-frontmatter-main-topic.md` — **status:
  closed, resolution: implemented**, closed 2026-06-05. Contradicts the
  roadmap's "Phase 5... depends on Phase 0b... request stays open P2/P3"
  framing. The frontmatter/validator/CLI surface (`NoteFrontmatter.main_topic`,
  `check_main_topic_against_db`, `--strict-main-topic`, `notes link
  --main-topic`) is done; only a **residual polish item** remains, noted
  in-file: concept cross-check is discipline-area-scoped
  (`schemas.py:417-474`) rather than exact `Concept.main_topic_id ==
  main_topic` equality. Phase 5's real scope (propagating Tag/MainTopic into
  `GraphNode`/collectors) is a **separate, still-open** concern — the
  roadmap conflated "note frontmatter field" (closed) with "graph node
  carries real tag/topic metadata" (open, see `_filter_by_tags` docstring at
  `graph/cli.py:217-219`: *"`GraphNode` does not carry DB-level tag data,
  this uses the node label as a best-effort proxy"*). That docstring is the
  correct Phase 5 anchor.
- `tasks/requests/2026-06-26-figure-extract-pdf-bbox/` — **directory does not
  exist** (`find` returned nothing under `tasks/requests/` for
  `*figure*`/`*bbox*`/`*pdf*`). **[UNCLEAR]**: the roadmap's post-candidatura
  backlog cites this path as "spec ready" — it is not present in the repo at
  this path. Either the spec lives elsewhere (not found in this search) or it
  was never committed. Flagged in the Appendix; not blocking for in-window
  phases since it's post-freeze anyway.
- `tasks/requests/2026-07-03-convention-engine-batch-transform.md` — confirmed
  `status: open`, `priority: P3`, `blocked_by: ["ADR pending
  (post-candidatura)", "candidatura exam (nov 2026)"]`. Explicit marco/no-op
  request; nothing to plan here beyond the Appendix one-liner.

---

## Target / design

Five in-window phases (0–4, freeze-safe stopping points after each) plus an
ordered post-freeze appendix. Phase 0 is pure hygiene (docs + refactor, no
behavior change). Phase 1 delivers the highest-value feature
(`build-exam --balanceo`) as its own request-doc-then-implementation cycle.
Phase 2 bundles two small, independent exercise QoL flags. Phase 3 is a
**verification-only** step now that `course add-practice` is confirmed
shipped. Phase 4 is a scheduling action (decision conversation), not code.

### Commands / API surface (target state after Phases 1–3)

```bash
workflow exercise build-exam --taxonomy-level ... --balanceo [--json] [--fail-under N]
workflow exercise list --chapter <chapter_number>
```

Expected `--balanceo --json` shape (indicative, locked in Phase 1's request doc):

```json
{
  "matrix": [
    {"taxonomy_level": "recordar", "taxonomy_domain": "informacion", "count": 4, "points": 40.0}
  ],
  "concept_coverage": {"total_concepts": 6, "distinct_covered": 4},
  "warnings": ["Slot (aplicar, procedimiento_mental): requested 3, found 1."]
}
```

---

## Resolved design rules

- **Phase ordering is locked by the director** (see task prompt) — do not
  reorder. Only intra-phase sequencing (which TDD step first) is this plan's
  discretion.
- **Phase 0 is a no-op-if-already-true check first**: verify before touching
  anything, since the ADR-INDEX and main-topic assumptions in the roadmap
  are already partly stale (see anchors above). ★ Confirm with user whether
  Phase 0a should be skipped entirely given ITEP-0013 is already `Accepted`.
- **Phase 1 balance matrix is additive**: `ExamDocument` gains an optional
  field (or a sibling return value) — it must not break the existing
  `build_exam()` callers/tests. Prefer a new `compute_balance(selection,
  session) -> BalanceReport` pure function in a new module
  (`workflow.exercise.balance`) over mutating `ExamDocument`, so Phase 1 has
  zero risk to `exam_builder.py`'s existing contract.
- **Fallbacks**: exercises with no resolved concept links count as `0` toward
  `concept_coverage`, not an error — mirrors the "warning, not fail" tone of
  Bundle A/B's non-strict paths.
- **Phase 2 `--chapter` collision**: an exercise whose `book_id` matches
  multiple `BibContent` rows spanning overlapping `first_exercise`/
  `last_exercise` ranges (data-entry error) — resolve by taking the first
  matching row and warn to stderr; do not silently pick arbitrarily. ★ Needs
  user confirmation this fallback is acceptable, since it's a new
  disambiguation rule not covered by existing precedent.
- **Phase 3 is a verification gate, not an implementation phase.** If
  `workflow course add-practice --help` matches the roadmap's ask exactly, close
  the request as "already shipped" (same disposition pattern as slugs #8/#12/#13
  in the roadmap's audit table) rather than write new code.

---

## Decisions — LOCKED (director, 2026-07-03)

1. Phase order fixed: 0 (hygiene) → 1 (`--balanceo`) → 2 (`\exa` lint +
   `--chapter`) → 3 (course add-practice verification) → 4 (concept-slug
   decision scheduling) → Appendix (post-freeze, unordered detail).
2. Phase 1 gets its own request doc from `data/templates/request-template.md`
   before implementation (audit slug #17 has no request file yet).
3. TDD RED→GREEN→REFACTOR + reviewer-esquema before every commit; model
   routing opus=review/sonnet=TDD/haiku=git-ops, unchanged from Bundles A/B/D.
4. No new ADR required for Phases 1–3 (additive CLI flags + pure functions,
   no schema/contract break). Phase 0a's ADR-INDEX edits are docs-only.

---

## Phases

### Phase 0 — hygiene carry-over

**Goal:** Close the two carry-over items from the pre-candidatura roadmap
without touching behavior, and correct the plan's own stale assumptions
before they propagate.

#### 0a. ADR INDEX hygiene

**Goal:** Confirm `docs/ADR/INDEX.md` accurately reflects ITEP-0013/0014/0015
status; fix only what's actually wrong.

**Verification steps (no RED/GREEN — docs only):**

- Re-read `docs/ADR/INDEX.md:82-84` — confirmed today: ITEP-0013 =
  `Accepted`, ITEP-0014 = `Proposed`, ITEP-0015 = `Proposed`. All three rows
  **already exist**.
- ★ Ask user: does the roadmap's "ITEP-0013 Proposed→Accepted" instruction
  refer to a state that's already resolved (likely — INDEX.md shows
  `Accepted` now), or is there a *different* ITEP-0013 file
  (`docs/ADR/ITEP-0013-note-relation-graph.md`) whose own frontmatter/status
  line disagrees with INDEX.md? Check that file's own header if this phase
  is picked up.
- If the individual ADR file's status line matches INDEX.md, **this phase is
  a no-op** — close it as "verified, no change needed" and move on.

**Commit point:** none needed if no-op; if the individual ADR file disagrees,
a single-line docs commit fixing the frontmatter `status:` field.

#### 0b. `graph/cli.py` filter helpers → `graph/filters.py`

**Goal:** Pure refactor — move `_build_full_graph`, `_expand_by_depth`,
`_parse_cluster_name`, `_filter_by_cluster`, `_filter_by_tags`
(`graph/cli.py:105-238`) into a new `src/workflow/graph/filters.py`. No
behavior change; existing tests must pass unmodified or with import-path-only
edits.

**RED tests** (no new test *behavior* — this is a refactor, so RED means
"tests currently pass against `graph.cli`; after the move they must still
pass, ideally with a re-export shim so the import line doesn't even need to
change"):

- Run `tests/workflow/test_graph_export.py` **before** the move — confirm
  green baseline (`TestExpandByDepth`, `TestClusterFilter`, `TestTagFlags`
  currently import `_expand_by_depth` from `workflow.graph.cli` at line 17).
- After the move, re-run the same file unmodified first (if `graph/cli.py`
  re-exports the four names via `from workflow.graph.filters import
  _expand_by_depth, _filter_by_cluster, _filter_by_tags,
  _parse_cluster_name`) — zero test edits needed. This is the preferred
  path per "Minimal Impact" coding-style rule.
- If re-export is rejected (cleaner boundary preferred), update
  `test_graph_export.py:17`'s import line only — no test logic changes.

**GREEN impl** — files touched:

- `src/workflow/graph/filters.py` (new) — houses `_build_full_graph`,
  `_expand_by_depth`, `_parse_cluster_name`, `_filter_by_cluster`,
  `_filter_by_tags`, moved verbatim (same signatures, same docstrings).
- `src/workflow/graph/cli.py` (edit) — delete the moved function bodies
  (lines ~105-238), replace with `from workflow.graph.filters import (...)`
  and keep call sites (`export_tikz_cmd` lines 527, 534, 538) unchanged.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P0b.
This is the only Phase 0 sub-item guaranteed to need a commit.

---

### Phase 1 — `exercise build-exam --balanceo` (#17)

**Goal:** Prove a taxonomy×concept balance matrix can be computed over an
assembled exam's `SelectionResult`, surfaced as table/CSV/JSON, with
warn/fail thresholds — the highest `volumen_futuro` item (every exam, every
cycle, during the freeze).

**Step 0 — write the request doc first** (none exists; audit slug #17 has no
file). Copy `data/templates/request-template.md` →
`tasks/requests/2026-07-03-exercise-build-exam-balanceo.md`. Fill: `id:
20260703-exercise-build-exam-balanceo`, `labels: [cli, exercise]`,
`components: [workflow.exercise]`, `related_requests:
["20260703-exercise-composability-flags"]` (shares `--json` precedent),
`priority: P1`. Acceptance criteria should mirror the JSON shape sketched
above under Target/design.

**RED tests** (`tests/workflow/exercise/test_balance.py`, new):

- `compute_balance(selection)` given a `SelectionResult` with 2 slots (one
  fully filled, one under-filled) returns a matrix row per slot with
  `count`/`points` matching `len(exercises)` and `points_per_item * count`.
- Concept coverage: given exercises with `ExerciseConcept` rows resolved via
  a session query, `distinct_covered` counts unique `concept_id`s across all
  selected exercises; `total_concepts` is a caller-supplied denominator
  (e.g. total concepts tagged to the course/topic) — **★ needs user
  confirmation**: what is `total_concepts` scoped to? (all concepts in DB?
  concepts tagged on the pool passed to `select_exercises`? Simplest correct
  default: distinct concepts appearing anywhere in the exercise **pool**
  passed to `build_exam_cmd`, not the whole DB.)
  the exercise pool, not the whole DB — resolves the ★ above without a
  blocking question.
- `--fail-under` threshold: an exit-code-2 case when e.g. `distinct_covered /
  total_concepts` falls below a caller-supplied float; exit-0 when at/above.
- `--json` output includes `matrix`, `concept_coverage`, `warnings` (reusing
  `selection.warnings`, per the composability precedent from Bundle B).
- CSV output: one row per slot, columns `taxonomy_level,taxonomy_domain,
  count,points`.

**GREEN impl** — files touched:

- `src/workflow/exercise/balance.py` (new) — `BalanceRow`, `BalanceReport`
  dataclasses; `compute_balance(selection: SelectionResult, session: Session)
  -> BalanceReport` — pure-ish (one session query for concept links via
  `ExerciseConcept`, no writes).
- `src/workflow/exercise/cli.py` (edit, extends `build_exam_cmd` at
  654-750) — add `--balanceo` flag (bool), `--json` flag (reuse Bundle B's
  precedent), `--fail-under FLOAT` (optional), `--csv PATH` (optional
  output). When `--balanceo` is set, compute and print the report instead
  of / alongside the exam body (★ confirm: does `--balanceo` replace the
  `.tex` output or run alongside it? Recommend: alongside, printed to
  stderr like existing warnings, so `--output` still captures clean `.tex`).
- `CLAUDE.md` — update the `build-exam` line in the exercise-CLI bullet list.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1.

**Verification:**

```bash
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q tests/workflow/exercise/test_balance.py --ignore=tests/test_database.py
uv run flake8 src/workflow/exercise/ tests/workflow/exercise/ --max-line-length=127 --max-complexity=10
workflow exercise build-exam -l recordar -d informacion --balanceo --json
```

**Est. size:** M (new module + CLI flags + request doc). **Unblocks:** every
subsequent exam assembly during the freeze gets balance visibility without a
manual spreadsheet pass — directly matches the stated `volumen_futuro`
rationale.

---

### Phase 2 — small exercise QoL pair (#5 `\exa` lint-units + `--chapter` filter)

**Goal:** Two independent, small, high-daily-use flags in the same module.
Ship separately if time runs short — they do not depend on each other.

#### 2a. `\exa` lint-units

**RED tests** (`tests/workflow/validation/test_exa_units.py`, new):

- Parse `share/latex/sty/SetUnits.sty` for all `\DeclareSIUnit\<name>{...}`
  declarations (regex, since no existing brace-counting helper targets
  `.sty` macro tables — confirmed gap) → whitelist set including at least
  `barn`, `fbarn`, `ace`, `vel`, `denV`, `denA`, `denL`, `angvel`, `angace`,
  `psi` (all present, `SetUnits.sty:17-40`).
  numeric literal followed by an *undeclared* unit token) flags it; a known
  siunitx built-in (`\si{\meter}`) or a declared custom unit does not.
- CLI/validator surface: **★ needs user confirmation** — is this a new
  `workflow validate exercises --lint-units` sub-check, or a standalone
  `workflow exercise lint-units` command? Recommend folding into the
  existing `validate exercises` pass (same fail-loud precedent as Bundle A)
  rather than a new top-level command.

**GREEN impl** — files touched:

- `src/workflow/latex/units.py` (new) — `load_declared_units(sty_path) ->
  frozenset[str]`, `find_undeclared_units(tex_body, declared) ->
  list[LintIssue]`.
- `src/workflow/validation/schemas.py` or `validation/cli.py` (edit) — wire
  the new check into the existing validator pass, gated the same way the
  unknown-frontmatter-key warning is (`schemas.py:387-457`, Bundle A
  precedent) — warn by default, unless a `--strict-units` flag is added
  (mirrors `--strict-concepts`).

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P2a.

#### 2b. `exercise list --chapter`

**RED tests** (extend `tests/workflow/exercise/test_cli.py` or equivalent):

- Given an `Exercise` with `book_id` pointing to a `BibEntry` that has a
  `BibContent` row with `chapter_number=3, first_exercise=1,
  last_exercise=20`, and the exercise's `exercise_id` numeric suffix (e.g.
  `phys-gauss-005` → `5`) falls in `[1,20]` → `--chapter 3` includes it.
- Exercise with no `book_id` (self-authored) is excluded when `--chapter` is
  passed (never matches), included when `--chapter` is omitted.
- Overlapping-range collision case (per Resolved Design Rules above): warn
  to stderr, take first match — needs a fixture with two overlapping
  `BibContent` rows for the same `bib_entry_id`.

**GREEN impl** — files touched:

- `src/workflow/exercise/service.py` or a new helper in
  `src/workflow/exercise/repos.py`(wherever `SqlExerciseRepo` lives —
  **[UNCLEAR] verify exact repo file path before implementing**, only
  imported as `SqlExerciseRepo` in `cli.py`, not yet located in this pass) —
  add `filter_by_chapter(exercises, chapter, session)` performing the
  `Exercise.book_id == BibContent.bib_entry_id` join + numeric-suffix range
  match.
- `src/workflow/exercise/cli.py` (edit, `list_exercises` at 246-310) — add
  `--chapter INT` option, apply the new filter after `repo.find_by_filters`.
- `CLAUDE.md` — update `exercise list` bullet.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P2b.

**Verification (both 2a/2b):**

```bash
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q tests/workflow/validation/test_exa_units.py tests/workflow/exercise/ --ignore=tests/test_database.py
uv run flake8 src/workflow/latex/ src/workflow/exercise/ src/workflow/validation/ --max-line-length=127 --max-complexity=10
workflow validate exercises --lint-units   # or final agreed surface
workflow exercise list --chapter 3
```

**Est. size:** S (`\exa` lint) + M (`--chapter`, upgraded from the roadmap's
assumed S due to the `BibContent` join complexity found above). **Unblocks:**
daily exercise-authoring friction reduction; `--chapter` also de-risks Phase
1's balance matrix by giving a chapter-scoped pool query pattern to reuse.

---

### Phase 3 — `course add-practice` verification (#14)

**Goal:** Confirm the roadmap's premise is stale — `course add-practice`
(`src/workflow/evaluation/cli.py:360-403`) is **already shipped**, not
"post-window P2, surface decision needed." Close the audit slug rather than
implement.

**Verification steps (no RED/GREEN expected):**

```bash
workflow course --help
workflow course add-practice --help
```

- Confirm live `--help` output matches the coded signature: `COURSE_CODE
  --name TEXT --week INT --type [practice|quiz] [--serial INT] [--file PATH]
  [--json]`.
- Check `list_practices`/`course practices` (`cli.py:413-431`) as the
  companion read-path — also already shipped.
- **If** the live surface differs from what slug #14's original gap wanted
  (e.g. missing a `--dc` or `--week-offset` flag matching the Bundle
  D-scaffold naming convention), file a **small, scoped follow-up request**
  documenting the delta — do not silently expand scope into a new feature.
- If it matches, update the roadmap/audit table disposition for #14 to
  "✅ closed — verified live, same pattern as #8/#12/#13" (same closure style
  already used for those three slugs in
  `tasks/roadmap/2026-07-03-pre-candidatura-window-roadmap.md`).

**Commit point:** docs-only (roadmap annotation) — no code commit expected
unless a gap is found.

**Est. size:** XS (verification only). **Unblocks:** removes a phantom
P2 item from the backlog, freeing real Phase-3 time for whichever of
Phase 1/2 needs it if they overrun.

---

### Phase 4 — concept-slug decision gate (#18)

**Goal:** Schedule the A/B/C architecture decision conversation with the
user — **not implementation**. `concepts.slug` vs Spanish-label collision
handling has three options per the roadmap; council decision requires the
user, not code.

**Steps:**

- Prepare a short options brief (A/B/C, one paragraph each) from the
  original request/audit source (`~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md`,
  slug #18 — **not re-read in this pass; cite path for whoever picks this up**).
- Present via `AskUserQuestion` (or equivalent) during a live session — do
  not pre-decide.
- Once decided, **file it as a locked decision** in a new or existing
  `tasks/requests/` doc, then it becomes a normal implementation phase
  (post-freeze, likely).

**No commit expected this phase** — it's a scheduling/decision action.

**Est. size:** XS (conversation only). **Unblocks:** every future
`concept add --code` interaction currently ambiguous between slug and label
conventions.

---

## Risks / out of scope

- **In scope:** Phases 0–4 as detailed above, strictly in the locked order.
- **Out of scope:** R4 convention engine (explicitly `blocked_by` ADR +
  candidatura per its own request frontmatter — do not touch); Bundle C
  reposición; PDF pipelines (spec path not found — see anchor note); any
  work on `\exa` beyond the lint-units check (e.g. auto-fix/rewrite is a
  different, larger feature).
- **Risk:** Phase 1's `total_concepts` denominator ambiguity (marked ★) could
  silently produce a misleading percentage if implemented without
  confirming scope — resolved above by defaulting to "distinct concepts in
  the pool", but flag this explicitly in the request doc's acceptance
  criteria so it's not re-litigated mid-TDD.
- **Risk:** Phase 2b's repo-file location for `SqlExerciseRepo` was not
  pinned down in this pass (only its import site in `cli.py` was found) —
  the implementer must `grep -rn "class SqlExerciseRepo"` before writing
  `filter_by_chapter` to avoid guessing a path.
- **Risk:** Phase 0a may be entirely moot (ITEP-0013 already `Accepted` in
  INDEX.md) — verify before spending any time on it; do not manufacture a
  change to justify the roadmap line item.
- No schema migration expected in Phases 0–3 (all new columns, if any, are
  computed at query time via existing FKs — `BibContent.first_exercise`/
  `last_exercise` already exist).

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# Live dry-run examples (on a COPY of the live DB, never the original)
# cp ~/01-U/workflow/workflow.db /tmp/workflow-test.db
# WORKFLOW_DATA_DIR=/tmp workflow exercise build-exam -l recordar -d informacion --balanceo --json
# WORKFLOW_DATA_DIR=/tmp workflow exercise list --chapter 3
# WORKFLOW_DATA_DIR=/tmp workflow course add-practice --help
```

---

## Appendix — post-freeze order (not detailed, one-liner rationale each)

1. **R4 convention engine / batch transform** (ADR first) — architecture item,
   explicitly `blocked_by` an ADR and the candidatura exam per its own
   request frontmatter (`tasks/requests/2026-07-03-convention-engine-batch-transform.md`);
   highest structural value but zero calendar pressure once Bundles A/B/D
   land, per the request's own rationale.
2. **PDF pipelines** (`exercise extract --pdf`, `figure extract --bbox`) —
   heavy new deps (PDF parsing), and the roadmap's cited spec path
   (`tasks/requests/2026-06-26-figure-extract-pdf-bbox/`) **was not found in
   this repo** — needs re-location or re-authoring before it can be
   estimated at all.
3. **Bundle C reposición** (#9 `exercise clone --variant`, #10 `build-exam
   --reposicion`) — user-deferred this window; same exam-assembly module as
   Phase 1, natural follow-on once `--balanceo` lands.
4. **ITEP-0014 fm_hash incremental-sync spike** — parked by its own ADR gate
   (status `Proposed`, confirmed `docs/ADR/INDEX.md:83`); needs the ADR
   decided first, independent of freeze timing.
5. **Bibliography Wave B** (bib-block stdin import) — smallest post-freeze
   item, self-contained to `workflow.prisma`/bib CLI, no cross-module
   dependency.
6. **PRISMA Wave C** — needs its own C0 request rewrite first per the
   roadmap; blocked on a docs step, not code.
7. **`\exa` follow-ups** (beyond lint-units, e.g. auto-fix) — natural
   extension of Phase 2a once the lint pass proves the unit-whitelist
   approach works in practice.
