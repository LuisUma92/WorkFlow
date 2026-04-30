---
id: 2026-04-29-main-topic-discipline-area-fk
title: Add NOT NULL FK from main_topic.discipline_area_id to discipline_area.id
type: enhancement
source_agent: user
opened_on: 2026-04-29
status: open
priority: P0
severity: blocker
labels: [db, validation]
components: [workflow.db, itep]
adr_refs: [ITEP-0008, ITEP-0010]
related_requests: [2026-04-29-evaluations-schema-migration]
related_gaps: []
notes: |
  ITEP-0008 amendment (in-place). State (`MainTopic`) and catalog
  (`DisciplineArea`) currently overlap at the area level with no DB-level
  guarantee that a `MainTopic` row's code maps to a real catalog row.
  Live DB on 2026-04-29 had 14 zombie main_topic rows with 4-char codes
  (`01MM`, `10MC`, ...) that no validation caught — wiped during Phase 0.
  This request closes the structural gap by making the catalog link a
  hard FK constraint, enforced both at schema level and in
  inittex.create_general.
acceptance_criteria:
  - "main_topic table has discipline_area_id INT NOT NULL FK -> discipline_area.id"
  - "MainTopic SQLAlchemy model declares the relationship with eager-friendly default"
  - "inittex.create_general resolves DisciplineArea by 6-char code, aborts on miss with pointer to 'workflow db taxonomy list'"
  - "project-level MainTopic inherits discipline_area_id from parent area row"
  - "invariant: MainTopic.code[:6] == MainTopic.discipline_area.code (asserted in inittex + checked in tests)"
  - "migration 0002_main_topic_discipline_area_fk in src/workflow/db/migrations/global/ ships the column add (idempotent, NOT NULL safe given empty table)"
  - "tests under tests/workflow/db/ cover: FK NOT NULL constraint, FK referential integrity, inittex aborts on unknown DDTTAA, project-level inheritance"
  - "ITEP-0008 ADR amendment committed alongside the migration"
verification:
  - "pytest tests/workflow/db/test_main_topic_discipline_area_fk.py -v"
  - "pytest tests/itep/test_create_general_catalog_link.py -v"
  - "sqlite3 ~/.local/share/workflow/workflow.db 'PRAGMA foreign_key_list(main_topic);' shows discipline_area_id FK"
---

# Add NOT NULL FK from `main_topic.discipline_area_id` to `discipline_area.id`

## Context

ITEP-0008 introduced two related tables in `workflow.db`:

- `discipline_area` — immutable catalog (~233 rows) loaded from
  `data/DD-*Codes.csv`. Source of truth for valid `DDTTAA` codes.
- `main_topic` — mutable project hierarchy (area-level rows with
  `parent_id=NULL`, project-level rows with `parent_id=area_id`). Code
  is 6 chars at area level and 10 chars (`DDTTAAYYPP`) at project level.

The split is intentional (catalog vs state, see ITEP-0008 §"Catalog vs
State: why two tables") but the DB has **no constraint** linking a
`MainTopic` row to a real `DisciplineArea`. Phase 0 audit on 2026-04-29
revealed 14 stale `main_topic` rows with 4-char codes (`01MM`, `10MC`,
`60FN`, ...) — pure pre-ITEP-0008 leftovers that no validation caught.
Wiping them was safe because nothing referenced them, but nothing
**prevents** the same drift recurring.

## Proposal

Add `MainTopic.discipline_area_id INT NOT NULL FK -> discipline_area.id`
and enforce the matching invariant in `inittex.create_general`.

### Schema

```python
class MainTopic(GlobalBase):
    ...
    discipline_area_id: Mapped[int] = mapped_column(
        ForeignKey("discipline_area.id"), nullable=False
    )
    discipline_area: Mapped["DisciplineArea"] = relationship()
```

### Migration

`src/workflow/db/migrations/global/0002_main_topic_discipline_area_fk.py`
under the ITEP-0010 runner:

```sql
ALTER TABLE main_topic
  ADD COLUMN discipline_area_id INTEGER NOT NULL
  REFERENCES discipline_area(id);
```

Live DB has 0 main_topic rows post-Phase-0 wipe, so NOT NULL is safe
without a backfill clause. Future re-applications on populated DBs are
out of scope for this request (no other live DB is known).

### Invariants (enforced in `inittex.create_general`)

- area-level row: `MainTopic.discipline_area_id` points to row whose
  `code` equals `MainTopic.code[:6]`,
- project-level row: `MainTopic.discipline_area_id` equals the parent
  area row's `discipline_area_id` (inheritance, not lookup),
- on unknown `DDTTAA`: abort with
  `"unknown discipline area '{code}'. Run: workflow db taxonomy list"`.

## Acceptance criteria

See frontmatter `acceptance_criteria`.

## Out of scope

- Backfill logic for non-empty `main_topic` tables on other installs
  (no such install known).
- Renaming or restructuring `DisciplineArea` itself.
- Collapsing the two tables into one (rejected — see ITEP-0008
  §"Catalog vs State: why two tables").
- Adding a similar FK from `Topic.main_topic_id` (already FK).

## Implementation notes

- Phase 1A (ITEP-0010 runner + baseline) **MUST** ship before this
  migration; the FK ships through the runner, not as a one-off.
- Tests live under `tests/workflow/db/` and `tests/itep/`. Use a
  throw-away SQLite seeded with a minimal `discipline_area` fixture.
- `inittex.naming` already validates `DDTTAA` shape; this request
  upgrades shape-validation to existence-validation.

## Progress log

- 2026-04-29 — opened by user after Phase 0 audit revealed catalog/state
  drift. Status `open`, priority `P0`, blocks `evaluations-schema-migration`
  in migration order.
