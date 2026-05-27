---
id: 20260526-database-normalization
title: Main database normalization
type: enhancement
source_agent: None
opened_on: 2026-05-26

status: open
resolution:
priority: P1
severity: bad-design

labels:
  - sqlite
  - zettelkasten
  - schema
  - migration

components:
  - workflow.db.models
  - workflow.db.models.knowledge
  - workflow.db.models.academic
  - workflow.db.models.notes
  - workflow.db.models.exercises
  - workflow.db.models.bibliography
  - workflow.concept
  - workflow.validation
  - workflow.exercise
  - workflow.vault

adr_refs:
  - ITEP-0002
  - ITEP-0009
  - ITEP-0010
  - ITEP-0012
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release: v1.8.1
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - New `workflow.db.models.knowledge` module owns `DisciplineArea`, `MainTopic`, `Topic`, `Content`, `Concept`; `academic.py` keeps only `Institution` + course/eval tables; `bibliography.py` owns `BibContent`; `notes.py` no longer defines `Concept`.
  - `Concept.content_id` FK (RESTRICT) replaces `Concept.main_topic_id`; `Concept.domain` column added with `ck_taxonomy_domain` CHECK against `_TAXONOMY_DOMAINS`.
  - `BibContent` carries `chapter_number`, `section_number`, `first_page`, `last_page`, `first_exercise`, `last_exercise` (moved off `Content`); `Content` reduced to `topic_id` + `name`.
  - `Exercise.concepts` JSON column and `Exercise.content_id` FK removed; M2M `ExerciseConcept(exercise_id, concept_id)` table replaces them.
  - SQLAlchemy mapper configures cleanly — no `back_populates` mismatches, no missing imports, no orphan relationships. `Base.metadata.create_all()` succeeds on a fresh DB.
  - Forward-only migration (ADR ITEP-0010) ships under `src/workflow/db/migrations/` and: (a) creates new tables, (b) backfills `BibContent` columns from old `Content` rows, (c) rebuilds `Concept` rows under the new schema preserving `code`/`label`/`parent_id`, (d) builds `ExerciseConcept` rows from the legacy `Exercise.concepts` JSON + `Exercise.content_id`, (e) drops the deprecated columns/tables, (f) bumps `schema_version`.
  - Migration is idempotent and reversible to a `.bak` snapshot in `~/01-U/workflow/`; dry-run mode prints planned row counts without writing.
  - Integration audit: `workflow concept *`, `workflow validate notes`, `workflow notes link --concept`, `workflow notes sync`, `workflow exercise *`, `workflow graph *`, `workflow vault *` all import the new module paths and pass their existing test suites against the migrated DB.
  - Repository protocols (`workflow.db.repos.protocols`) updated for the new `ExerciseConcept`/`BibContent` shape; no raw SQL leaks through.
  - Full test suite green on the live DB (`~/01-U/workflow/workflow.db`) after migration; ≥80% coverage on new/changed code (lessons: reviewer-esquema 4× parallel).
  - ADR ITEP-0002 (four-layer schema) updated to reflect the new module split; new ADR or ITEP-0012 amendment documents `Concept.content_id` + `ExerciseConcept`.

verification:
  - `pytest -q` green, including the 1146+ baseline and new migration/integration tests.
  - `python -c "from workflow.db.models import *; from sqlalchemy import create_engine; from workflow.db.base import GlobalBase; GlobalBase.metadata.create_all(create_engine('sqlite:///:memory:'))"` exits 0.
  - Dry-run migration on a copy of `~/01-U/workflow/workflow.db` reports zero row loss; post-migration row counts match pre-migration for `concept`, `exercise`, `bib_content`, `note_concept`.
  - `workflow validate notes --strict-main-topic --strict-concepts` returns 0 on the live vault after migration.
  - `workflow graph stats` produces the same node/edge totals (±expected delta from new `ExerciseConcept` edges) as pre-migration.
  - `flake8` lint clean (max-line-length 127, max-complexity 10).
  - Re-run audit (`workflow_audit_YYYYMMDD.txt` style dump) and confirm: no orphan FKs, no duplicate definitions of `Concept`/`MainTopic`/`BibContent`, `schema_version` bumped.
---

# Request: Review database models changes

## Context

DB state at commit `5f02e75` audited at `~/01-U/workflow/workflow_audit_20260523.txt`.
Audit surfaced inconsistencies: `Concept` and `BibContent` mis-located (in `notes.py` and
`academic.py` resp.), `Content` carrying chapter/section/page/exercise-range columns that
belong to the `BibEntry`↔`Content` link, `Exercise.concepts` stored as opaque JSON instead
of an M2M, and `Concept` rooted at `MainTopic` rather than at the bibliographic `Content`
it actually concerns.

Commit `8591429` ("Init normalization process") restructures the ORM:

- New module `src/workflow/db/models/knowledge.py` owns `DisciplineArea`, `MainTopic`,
  `Topic`, `Content`, `Concept`.
- `academic.py` reduced to `Institution` + course/evaluation templates.
- `bibliography.py` gains `BibContent` and absorbs chapter/section/page/exercise-range
  columns from old `Content`.
- `notes.py` drops `Concept` (now imported from `knowledge`).
- `exercises.py` drops `Exercise.concepts` (JSON) and `Exercise.content_id`; adds
  `ExerciseConcept` M2M table.
- `Concept` re-rooted: `content_id` FK (RESTRICT) replaces `main_topic_id`; new `domain`
  column with `ck_taxonomy_domain` CHECK.

Models commit is **schema-only**: no migration, no integration updates, and the commit
contains residual bugs that must be fixed as part of this work — see *Implementation
notes*.

Scope of this request: (a) review the normalization, (b) fix the residual mapper/typo
bugs, (c) design and ship the forward-only migration, (d) audit and update every
integration that imports the moved/renamed symbols.

## Proposal

### Commands / API surface

Model surface (post-change):

- `src/workflow/db/models/knowledge.py` — `DisciplineArea`, `MainTopic`, `Topic`,
  `Content`, `Concept`
- `src/workflow/db/models/academic.py` — `Institution`, `Course`, `CourseContent`,
  `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation`
- `src/workflow/db/models/bibliography.py` — existing bib tables + `BibContent`
- `src/workflow/db/models/notes.py` — `Note`, `Citation`, `Label`, `Link`, `Tag`,
  `NoteTag`, `NoteConcept`, `NoteEdge` (no longer defines `Concept`)
- `src/workflow/db/models/exercises.py` — `Exercise`, `ExerciseOption`, `ExerciseConcept`

Migration CLI:

- New `workflow db migrate normalize-0008` (or next schema_version) — forward-only,
  with `--dry-run`, `--backup`, `--check` flags. Mirrors the style of prior
  ITEP-0010 migrations.

Integration points to re-wire (non-exhaustive — full audit is part of acceptance):

- `from workflow.db.models.notes import Concept` → `from workflow.db.models.knowledge import Concept`
- `from workflow.db.models.academic import MainTopic, Topic, Content, BibContent, DisciplineArea` → `from workflow.db.models.knowledge import ...` (and `BibContent` from `bibliography`)
- `workflow.concept.service.resolve_concepts` — verify still works with `content_id` root.
- `workflow.exercise.parser` / `workflow.exercise.cli` — replace JSON `concepts` writes with `ExerciseConcept` upserts; drop `content_id` reads.
- `workflow.validation` — `--strict-concepts` path must resolve against the new `Concept` shape.
- `workflow.graph.collectors` — `collect_note_concepts` and any future `collect_exercise_concepts` to use `ExerciseConcept`.
- `workflow.vault.unify` — no schema impact expected; verify ID-remap pass still finds `concept` rows.

### Shape of result

- One PR (or phase-stack) that lands: residual-bug fixes → migration → integration
  rewires → tests → ADR updates → tag bump (`v1.8.1`).
- Live `~/01-U/workflow/workflow.db` migrated in-place with a `.bak` snapshot under
  `~/01-U/workflow/`.
- `workflow_audit_<post>.txt` re-dump checked into `docs/audits/` (or referenced in the
  ADR) confirming no orphan FKs / duplicate definitions.

## Acceptance criteria

(See frontmatter `acceptance_criteria`.)

## Out of scope

- Renaming `Concept` to a different name or changing `code` slug semantics (ITEP-0012 locked).
- LZK-/PRISMA-side schema changes; only touch those models if a moved symbol is imported.
- Neovim plugin Lua rewires beyond import-path updates surfaced by failing tests.
- Performance tuning, new indexes beyond what's required for the new FKs.
- Backporting to pre-`v1.7.x` schema versions — forward-only per ADR ITEP-0010.

## Evidence / glue replaced

Diff stat of `8591429` (models only):

```
 src/workflow/db/models/__init__.py       |  11 +-
 src/workflow/db/models/academic.py       | 112 +----------------
 src/workflow/db/models/bibliography.py   |  20 +++
 src/workflow/db/models/exercises.py      |  25 ++--
 src/workflow/db/models/knowledge.py      | 139 +++++++++++++++++++++
 src/workflow/db/models/notes.py          |  38 +++----
```

Key structural deltas:

- `Concept`: `main_topic_id` (FK `main_topic.id`, RESTRICT) → `content_id` (FK `content.id`, RESTRICT); new `domain VARCHAR(40)` + CHECK constraint.
- `Content`: loses `chapter_number`, `section_number`, `first_page`, `last_page`, `first_exercise`, `last_exercise`.
- `BibContent`: gains those six columns (now the link table carries the citation locus).
- `Exercise`: loses `concepts TEXT` (JSON) and `content_id INTEGER` FK.
- `ExerciseConcept`: new M2M `(exercise_id, concept_id)` with CASCADE on both sides.

## Implementation notes

Residual bugs in `8591429` that the implementing PR must fix before migration design:

1. **Mapper mismatch in `knowledge.py`**: `Content.concepts` declares
   `relationship(back_populates="main_topic")` but the `Concept` side now exposes
   `content: Mapped["MainTopic"] = relationship(back_populates="concepts")` — both
   the `back_populates` target *and* the annotated type are wrong. Should be
   `Concept.content: Mapped["Content"]` with `back_populates="concepts"`, and
   `Content.concepts` should `back_populates="content"`.
2. **Missing imports in `knowledge.py`**: `Concept` references `datetime` and
   `DateTime` (for `created_at`) — neither imported. Module fails to load.
3. **Tablename typo**: `ExerciseConcept.__tablename__ = "exercise_contcept"`. Fix to
   `"exercise_concept"` (migration must use the corrected name).
4. **`ExerciseConcept` PK**: declares both an `id` primary key *and* composite PK on
   `(exercise_id, concept_id)`. Pick one — composite PK is cleaner and matches the
   M2M intent.
5. **Stale type hints / docstrings**: `knowledge.py` header says
   "AcademicArea, MainnTopic" and lists "Topic, Content, Content"; `Concept.content`
   is annotated as `MainTopic`.
6. **`__init__.py` re-export of `Concept`**: now sourced from `knowledge`; ensure
   `notes.__all__` no longer lists it (already done) and that no downstream module
   does `from workflow.db.models.notes import Concept`.

Migration design notes:

- Use SQLite `ALTER TABLE` only where safe; for column drops on `content`, `exercise`,
  and the `concept` re-root, follow the documented "create new → copy → drop old →
  rename" pattern already used by ITEP-0010 migrations.
- `Exercise.concepts` JSON backfill: parse list, map note-id / concept-slug semantics
  to `concept.id`, insert `ExerciseConcept` rows; log unresolved entries to stderr
  and continue (or fail under `--strict`).
- `Content` → `BibContent` column move: requires resolving which `BibEntry` each
  `Content` row was authored against. If `Content` was not already linked through
  `bib_content`, the migration must either (a) refuse and emit a report, or
  (b) synthesize a `bib_content` row under an explicit `--assume-bib <bibkey>` flag.
  Decide during planning.
- Snapshot `~/01-U/workflow/workflow.db` to
  `~/01-U/workflow/workflow.db.pre-normalize-0008.bak` before any write.

Methodology (locked, per global feedback):

- TDD: RED → GREEN → REFACTOR, ≥ 80% coverage on migration + new code.
- Reviewer-esquema: 4 parallel reviewers (python + security + tdd + architect),
  CRITICAL/HIGH inline.
- Commit + tag at end of each phase; update `~/.claude/primer.md`.

## Progress log

- 2026-05-26 — opened by Luis Fernando Umaña Castro after inspecting the current database `a693f1b`.
- 2026-05-26 — request body completed (scope, residual bugs, migration design, acceptance + verification criteria).

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [ ] All acceptance criteria met (frontmatter).
- [ ] All verification commands run green and recorded in progress log.
- [ ] Residual bugs 1–6 in *Implementation notes* fixed.
- [ ] Migration shipped, applied to live DB, `.bak` snapshot retained.
- [ ] ADR ITEP-0002 updated; ITEP-0012 amended (or new ADR opened) for `Concept.content_id` + `ExerciseConcept`.
- [ ] `schema_version` row bumped.
- [ ] Post-migration audit dump checked in / linked.
- [ ] `~/.claude/primer.md` updated with new milestone + next step.
- [ ] Push policy honored (`public` GitHub primary; `origin`/gitea only on `inm` LAN).
