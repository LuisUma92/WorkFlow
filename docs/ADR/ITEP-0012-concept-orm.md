---

id: ITEP-0012
title: "Concept ORM Surface"
aliases:
  - ADR-ITEP-0012
status: Implemented (Phase 5, migration 0009, 2026-05-27)
crated: 2026-05-06
authors:
  - "Luis Fernando Umaña Castro"
reviewers: []
tags:
  - architecture
  - zettelkasten
  - latexzettel
  - notes
decision_scope: 
  - module
related_adrs: []
type: "permanent"

---

## Context

The `Concept` and `NoteConcept` ORM models were already shipped in
`src/workflow/db/models/notes.py:192-223` and migration
`src/workflow/db/migrations/global/0005_add_note_tables.py:82-99`.

Phase B.1 added `main_topic_id` on `Note`, Phase B.2 added validators, and
Phase B.3 added `validate notes --strict-main-topic`. ITEP-0012 exposes the
Concept layer: a CLI surface, a resolver reused by the validator, and a new
`--strict-concepts` flag on `validate notes`.

---

## Decision

### 1. code is the canonical slug

`Concept.code` (max 32 chars, slug regex `^[a-z0-9][a-z0-9-]{0,31}$`) is the
canonical external identifier. The integer `id` is internal. All CLI
arguments and frontmatter `concepts:` list items use `code` slugs.

Rationale: codes are stable, human-readable, and match the pattern already
used by `MainTopic.code` (DDTTAA).

### 2. Frontmatter `concepts:` contains `Concept.code` slugs only

The `concepts:` YAML list in note frontmatter must be a list of code slugs
(e.g. `["newton-2nd", "forces"]`). Mixed label/code forms are rejected at
schema validation time.

Rationale: simple, unambiguous, consistent with Q1 resolution.

### 3. Parent must be within the same MainTopic

`Concept.parent_id` must reference a `Concept` row with the same
`main_topic_id`. The service enforces this on `add_concept`; the ORM FK does
not encode this constraint (SQLite limitation).

Rationale: prevents cross-topic hierarchy confusion; consistent with the
guideline in Phase B §9.

### 4. `concept add --main-topic` is required

The `main_topic_code` parameter is required on `add_concept` because
`Concept.main_topic_id` is NOT NULL at the DB level. There are no
"orphan" concepts.

### 5. `rm --force` reparents children to grandparent (Q4)

When `remove_concept(code, force=True)` is called and the target concept has
children, the service explicitly sets each child's `parent_id` to the removed
concept's own `parent_id` (grandparent) **before** the delete.

- If the removed concept was a root (parent_id=None), its children become roots.
- This overrides the schema-level `ON DELETE SET NULL` with an explicit
  service-side UPDATE, giving predictable tree semantics.
- `NoteConcept` rows are also deleted under `force=True`.

### 6. No new migration for ITEP-0012

The DDL was already applied in `global/0005`. No index is added at this time;
`ix_concept_main_topic_id` / `ix_concept_parent_id` can be added in a future
slot if `tree` or `list --main-topic` performance degrades.

---

## CLI Surface

```
workflow concept list    [--main-topic DDTTAA] [--json]
workflow concept show    CODE [--json]
workflow concept add     --code SLUG --label TEXT --main-topic DDTTAA
                         [--parent SLUG] [--description TEXT] [--json]
workflow concept tree    [--main-topic DDTTAA] [--json]
workflow concept rm      CODE [--force]
workflow concept rename  OLD_CODE NEW_CODE
```

---

## JSON Shapes (locked)

### `concept list --json`

```json
[
  {
    "code": "newton-2nd",
    "label": "Newton 2nd Law",
    "main_topic": "FI0006",
    "parent": "forces",
    "description": null,
    "id": 17
  }
]
```

### `concept show --json`

```json
{
  "code": "newton-2nd",
  "label": "...",
  "main_topic": "FI0006",
  "parent": "forces",
  "description": null,
  "id": 17,
  "child_count": 3,
  "created_at": "2026-05-06T12:00:00"
}
```

### `concept tree --json`

```json
[
  {
    "code": "forces",
    "label": "...",
    "children": [{ "code": "newton-2nd", "label": "...", "children": [] }]
  }
]
```

---

## Validator

`check_concepts_against_db(fm, session, *, strict: bool)` in
`src/workflow/validation/schemas.py` reuses `resolve_concepts` from the service
layer. It also checks that each resolved concept's `main_topic_id` matches
the note's resolved `main_topic_id` (mt-mismatch detection).

`validate notes --strict-concepts` is additive and orthogonal to
`--strict-main-topic`.

---

## Forward Dependencies

- `notes link --concept CODE` (Phase A follow-up) MUST reuse
  `concept.service.resolve_concepts`.
- Phase B.5 (`--strict-concepts` validator) is shipped as part of ITEP-0012.3.

---

## Consequences

**Good:**

- Clean service/CLI/formatter separation.
- Frontmatter concepts validated at `validate notes` time.
- Tree semantics on `rm --force` are explicit and predictable.

**Neutral:**

- No DB-level cross-topic parent enforcement (SQLite limitation).
- No migration slot consumed.

**Bad / risks:**

- Cross-DB FK fiction: `concepts:` in frontmatter refers to GlobalBase;
  per-note MD files don't have a DB FK. Validator-time enforcement only.

---

## Implementation Retrospective (2026-05-23)

The Concept ORM CLI surface (`concept list|show|add|tree|rm|rename`) and the `--strict-concepts` validator
flag shipped in earlier phases. Migration 0008 (v1.5.1) renamed `note_concept.tag_id` → `concept_id`,
repairing a legacy `create_all()` drift that predated ITEP-0012.

**P1** (`dc79b59`): `notes link --concept CODE` materializes a `NoteConcept` row via `upsert_note_concept()`.
Added `--remove` flag (drops frontmatter entry + deletes DB row, idempotent) and `--strict` flag (unknown
codes are errors rather than warnings). 18 new tests.

**P2** (`2340d38`): `notes sync` runs a per-note `_sync_note_concepts` pass (Pass 5) that reads the
frontmatter `concepts:` list and upserts `NoteConcept` rows. `SyncReport` gained a `concept_links_created`
counter. `--strict-concepts` flag propagates the `strict` parameter to `resolve_concepts`. 8 new tests.

**Known limitation:** stale `NoteConcept` rows are NOT pruned when frontmatter drops a concept code.
Removal requires explicit `notes link --concept CODE --remove`. A future `--prune` flag on `notes sync`
is deferred.

---

## Amendment 2026-05-27 — DB Normalization (migration 0009)

Migration `src/workflow/db/migrations/global/0009_normalize_models.py` (forward-only per ITEP-0010,
single atomic transaction) introduced the following changes to the Concept surface. Dangling
`Exercise.concepts` JSON was dumped to `~/01-U/workflow/migration-0009-orphan-exercise-concepts.txt`
before the column was dropped.

### Re-rooting: `content_id` replaces `main_topic_id`

`Concept.main_topic_id` (FK → `MainTopic`) has been replaced by `content_id` (FK → `Content`,
`ON DELETE RESTRICT`). `Content` sits one level below `MainTopic` in the hierarchy
(`MainTopic → Topic → Content`), giving concepts a more precise topical anchor.

### New `domain` column

`Concept` gains a `domain VARCHAR(40) NOT NULL` column with a CHECK constraint
(`ck_taxonomy_domain`) whose accepted values come from `_TAXONOMY_DOMAINS`:

- `Información`
- `Procedimiento Mental`
- `Procedimiento Psicomotor`
- `Metacognitivo`

### `Concept.main_topic` property + backward-compat forwarder

A `@property` `Concept.main_topic` traverses `content → topic → main_topic` and returns `None`
safely if any link is missing. The service layer exposes a thin `concept_main_topic(concept)`
forwarder for backward compatibility with callers that previously read `concept.main_topic_id`
directly.

### `ExerciseConcept` M2M shape

`Exercise.concepts` (JSON column) and `Exercise.content_id` (FK) are dropped. Topical linking
is now exclusively via `ExerciseConcept(exercise_id, concept_id)` with a composite PK and
`ON DELETE CASCADE` on both FKs. `exercise/service.py` sync resolves frontmatter concept slugs
via `resolve_concepts()` and upserts + sweeps `ExerciseConcept` rows. Strict mode
(`--strict-concepts`) raises on unknown slug; lenient mode warns and skips.

### CLI change: `workflow concept add`

| Before | After |
| ------ | ----- |
| `--main-topic DDTTAA` (required) | `--content-id INTEGER` (positive, `IntRange(min=1)`) + `--domain TEXT` (both required) |

**Note (deliberate defer):** `--content-id` accepts a raw integer because `Content.code` slug
lookup is not yet implemented. A future follow-up will add `--content-code SLUG` as the
human-friendly alias. Until then, callers must look up the integer PK from
`workflow db content list` (or equivalent).

### Open questions (not yet resolved — do not close)

1. **`Content.code` slug** — deferred. CLI uses numeric `--content-id` until a slug column is
   added to `Content` and a resolver is wired in.
2. **`Concept.domain` derivation rule** — independently assigned per concept vs. derived from
   `content.topic`. Policy not yet decided; currently caller-supplied.
3. **`workflow exercise sync` auto-create policy** — current policy: warn-and-skip (lenient) or
   raise (strict). Auto-creation of unknown concept slugs is explicitly NOT supported.
