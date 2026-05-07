# ADR ITEP-0012: Concept ORM Surface

**Status:** Accepted
**Date:** 2026-05-06
**Deciders:** Luis Fernando Umana Castro

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
canonical external identifier.  The integer `id` is internal.  All CLI
arguments and frontmatter `concepts:` list items use `code` slugs.

Rationale: codes are stable, human-readable, and match the pattern already
used by `MainTopic.code` (DDTTAA).

### 2. Frontmatter `concepts:` contains `Concept.code` slugs only

The `concepts:` YAML list in note frontmatter must be a list of code slugs
(e.g. `["newton-2nd", "forces"]`).  Mixed label/code forms are rejected at
schema validation time.

Rationale: simple, unambiguous, consistent with Q1 resolution.

### 3. Parent must be within the same MainTopic

`Concept.parent_id` must reference a `Concept` row with the same
`main_topic_id`.  The service enforces this on `add_concept`; the ORM FK does
not encode this constraint (SQLite limitation).

Rationale: prevents cross-topic hierarchy confusion; consistent with the
guideline in Phase B §9.

### 4. `concept add --main-topic` is required

The `main_topic_code` parameter is required on `add_concept` because
`Concept.main_topic_id` is NOT NULL at the DB level.  There are no
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

The DDL was already applied in `global/0005`.  No index is added at this time;
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
[{"code": "newton-2nd", "label": "Newton 2nd Law",
  "main_topic": "FI0006", "parent": "forces",
  "description": null, "id": 17}]
```

### `concept show --json`
```json
{"code": "newton-2nd", "label": "...", "main_topic": "FI0006",
 "parent": "forces", "description": null, "id": 17,
 "child_count": 3, "created_at": "2026-05-06T12:00:00"}
```

### `concept tree --json`
```json
[{"code": "forces", "label": "...", "children": [
   {"code": "newton-2nd", "label": "...", "children": []}
 ]}]
```

---

## Validator

`check_concepts_against_db(fm, session, *, strict: bool)` in
`src/workflow/validation/schemas.py` reuses `resolve_concepts` from the service
layer.  It also checks that each resolved concept's `main_topic_id` matches
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
  per-note MD files don't have a DB FK.  Validator-time enforcement only.
