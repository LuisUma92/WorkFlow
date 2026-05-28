---
id: 20260527-topic-reroot-discipline-area
title: Re-root Topic at DisciplineArea + MainTopicSyllabus join
type: enhancement
source_agent: None
opened_on: 2026-05-27

status: proposed
resolution:
priority: P1
severity: bad-design

labels:
  - sqlite
  - schema
  - migration
  - zettelkasten

components:
  - workflow.db.models
  - workflow.db.models.knowledge
  - workflow.db.maturation
  - workflow.validation
  - workflow.concept
  - workflow.graph
  - itep

adr_refs:
  - ITEP-0002
  - ITEP-0008
  - ITEP-0010
  - ITEP-0012
related_requests:
  - 2026-05-04-zettelkasten-main-topic-bundle
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release: v1.11.0
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - New `MainTopicSyllabus` ORM in `workflow.db.models.knowledge` with composite PK `(main_topic_id, topic_id)`, both FKs `ON DELETE CASCADE`, `week_no INTEGER NULL`, `order_no INTEGER NOT NULL`.
  - `Topic.main_topic_id` removed; `Topic.discipline_area_id` (FK→discipline_area, NOT NULL, RESTRICT) added. Unique constraint `(discipline_area_id, serial_number)` enforced on the table.
  - Migration `0011_topic_root_discipline_area.py` ships under `src/workflow/db/migrations/global/`, forward-only, idempotent, PRAGMA-guarded. Live DB has 0 topic rows — migration drops+recreates `topic` cleanly with the new shape and creates `main_topic_syllabus`.
  - Integration rewires — `workflow.db.maturation` queries traverse Topic→DisciplineArea (not Topic→MainTopic); `workflow.validation.schemas` Concept.main_topic chain updated (either via MainTopicSyllabus lookup or removed from strict-main-topic check, with ADR amendment); `workflow.concept.service.concept_main_topic()` deprecated/removed and all callers fixed; `workflow.graph.collectors` Topic edges use `discipline_area_id`; `src/itep/*` Topic creation switches from `main_topic_id` to `discipline_area_id`.
  - Tests: `_seed_concept_chain` helper rewritten — canonical chain is `DisciplineArea → Topic → Content`. MainTopic is no longer in the chain. Optional `_seed_main_topic_syllabus()` helper for tests that need the syllabus join.
  - Tests: at least 8 new tests covering migration shape, FK directions, MainTopicSyllabus CRUD + cascade, and canonical traversal DisciplineArea→Topic→Content.
  - ADR ITEP-0002 module ownership table refreshed to reflect the new Topic root and the new `MainTopicSyllabus` join table.
  - ADR ITEP-0008 amended: clarifies that the "two-layer directory" naming rule is unchanged; only the DB-level FK root of `Topic` changes.
  - ADR ITEP-0012 amended: notes that `Concept.main_topic` canonical chain now terminates at `DisciplineArea`; per-project MainTopic requires explicit context via `MainTopicSyllabus`.

verification:
  - "`python -c \"from workflow.db.models import *; from sqlalchemy.orm import configure_mappers; configure_mappers()\"` exits 0."
  - "`pytest -q --ignore=tests/test_database.py` green."
  - "`workflow db migrate status --base global --json` shows head at `0011_topic_root_discipline_area` after apply on a copy of live DB."
  - Row counts post-migration: `topic` still 0; `main_topic_syllabus` table created and empty.
  - "`workflow validate notes --strict-main-topic --strict-concepts` exits 0 on live vault."
---

# Request: Re-root `Topic` at `DisciplineArea` + introduce `MainTopicSyllabus` join

## Context

Today's schema (post-v1.8.1):

```
DisciplineArea (CSV-seeded reference, 6-char DDTTAA code)
   ↑
MainTopic       (per-project, code DDTTAA-YYPP)
   ↑
Topic           (name + serial_number) ← FK Topic.main_topic_id
   ↑
Content         (name)
   ↑
BibContent      (BibEntry ↔ Content + chapter/section/pages)
Concept         (FK content_id, after v1.8.1)
```

This forces Content + BibContent + Concept + Exercise links to live inside a single
project instance. Two MainTopics covering the same field require duplicate
Content/Concept rows, breaking dedup.

User decision (2026-05-27): Topic belongs to the **field** (DisciplineArea), not the
project instance. Project-iteration ordering moves into a new join table.

## Locked decisions

- `Topic.main_topic_id` (FK→main_topic) → `Topic.discipline_area_id`
  (FK→discipline_area, NOT NULL, RESTRICT).
- `Topic.serial_number` semantics: canonical chapter index within the area. Unique
  constraint `(discipline_area_id, serial_number)` recommended.
- New `MainTopicSyllabus(main_topic_id, topic_id, week_no, order_no)` join — composite
  PK `(main_topic_id, topic_id)`. `week_no INTEGER NULL`, `order_no INTEGER NOT NULL`.
  Both FKs `ON DELETE CASCADE`.
- Single forward-only migration `0011_topic_root_discipline_area`. Live DB has 0 topic
  rows → structural-only; migration can drop+recreate `topic` cleanly.
- `Concept.main_topic` property (currently `concept.content.topic.main_topic`) is no
  longer trivially derivable. After re-root, MainTopic for a concept is
  **project-context-dependent** — requires a `main_topic_id` argument. Old property
  either dropped or returns the canonical chain
  `Concept → Content → Topic → DisciplineArea`. The thin `concept_main_topic()`
  forwarder in `workflow.concept.service` becomes deprecated; replace callers.

## Proposal

### Target schema after migration

```
DisciplineArea (CSV-seeded reference, 6-char DDTTAA code)
   ↑
Topic           (name + serial_number, FK discipline_area_id RESTRICT)
   ↑                              ↑
Content         (name)            MainTopicSyllabus
   ↑                              (main_topic_id, topic_id, week_no, order_no)
BibContent      (BibEntry ↔ Content + chapter/section/pages)
Concept         (FK content_id)
```

`MainTopic` continues to exist as the per-project label (`DDTTAA-YYPP`), but its
relationship to `Topic` is now mediated by `MainTopicSyllabus` rather than a direct
FK on `Topic`.

### Integration points to rewire

- `workflow.db.maturation` — queries that walk `Topic.main_topic_id` must
  switch to `Topic.discipline_area_id`.
- `workflow.validation.schemas` — `--strict-main-topic` check that traverses
  `Concept.main_topic` chain must be updated or removed; decision requires ADR
  amendment (see open question 3).
- `workflow.concept.service.concept_main_topic()` — deprecated; callers identified
  and fixed during P3.
- `workflow.graph.collectors` — any edge built from `Topic.main_topic_id` uses
  `Topic.discipline_area_id` instead; optional new edge type for
  `MainTopicSyllabus` links if graph consumers benefit.
- `src/itep/*` (manager, naming, create) — if Topic rows are created with
  `main_topic_id`, switch to `discipline_area_id`.

### Methodology (locked)

- TDD: RED → GREEN → REFACTOR, ≥ 80% coverage on migration + new code.
- Reviewer-esquema: 4 parallel reviewers (python + security + tdd + architect),
  CRITICAL/HIGH inline.
- Commit + tag at end of each phase; update `~/.claude/primer.md`.

## Acceptance criteria

(See frontmatter `acceptance_criteria`.)

## Verification

(See frontmatter `verification`.)

## Out of scope

- Note↔MainTopic frontmatter binding (separate Phase 4C work — keep `MainTopic` as
  project tag on notes).
- Note↔Topic frontmatter binding (separate Phase 4D — canonical chapter tagging).
- Graph filters using new chain (Phase 4E).
- Backfilling MainTopicSyllabus rows from project config.yaml or lecture schedules
  (separate request).

## Open questions

1. Should `Topic.serial_number` be UNIQUE per `(discipline_area_id, serial_number)`,
   or just an ordering hint (non-unique)?
2. When a project iteration cites a Content via BibContent, does it implicitly add a
   MainTopicSyllabus row for the containing Topic? Or is syllabus explicit only?
3. Concept.domain rule (already an open question from v1.8.1) interacts: should
   `Concept.domain` derive from `Topic.discipline_area_id` (auto) or stay
   independently assigned? Defer to ITEP-0012 amendment.

## Implementation phases (suggested)

- P1: RED tests for new ORM shape + mapper config sanity.
- P2: ORM changes + migration `0011`. GREEN tests.
- P3: Integration rewires (maturation, validation, concept-service, graph, itep).
- P4: ADR amendments (ITEP-0002, ITEP-0008, ITEP-0012).
- P5: Live-DB migration trial + apply + tag (probably v1.11.0).

## Progress log

- 2026-05-27 — opened by Luis Fernando Umaña Castro; scope, locked decisions,
  integration map, acceptance + verification criteria written.
