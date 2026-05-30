# 0018 — `workflow topic import` bulk-import contract

- **Status:** Accepted
- **Date:** 2026-05-30
- **Domain:** Knowledge / CLI
- **Depends on:** ITEP-0012 (concept ORM), [0004](0004-sqlalchemy-orm.md) (SQLAlchemy 2.0)

## Context

`workflow topic import <file.yaml>` seeds a full `DisciplineArea → Topic →
Content → Concept` hierarchy from one YAML file, reusing the per-entity
`add_topic` / `add_content` / `add_concept` services (single source of truth for
creation + uniqueness rules). The CLI output shape and exit codes are now a
**public, agent-scriptable contract** (autonomous runners script against them),
so they are pinned here.

## Decision

### Exit codes
- **0** — full success, or a clean `--dry-run`.
- **1** — schema / YAML error, raised **before any write** (`ImportSchemaError`).
- **2** — unknown `discipline_area_code` (FK target missing), **before any write**.
- **3** — partial failure: one or more row-level errors were collected, other rows created.

### `--json` shape (pinned)
```json
{"created": {"topics": N, "contents": N, "concepts": N},
 "skipped": S,
 "errors": [{"entity": "topic|content|concept", "row": "<name|code>", "reason": "<msg>"}]}
```
(No `dry_run` field — `--dry-run` is conveyed by the human table line `[DRY-RUN] Would create …`; the JSON shape is intentionally minimal per the originating request.)

### Transaction & partial-failure semantics
One transaction per run. Two distinct failure classes:

1. **App-level row errors** (invalid `domain`, parent in a different content, etc.)
   are raised by `add_*` **before** the row is added to the session, so the
   session stays clean. These are collected as `RowError` and the run continues →
   partial success, **exit 3**, created rows committed.
2. **Genuine DB-integrity errors** at `flush()` (a constraint the app did not
   pre-check) are **NOT swallowed**. They propagate and abort the whole run; the
   CLI rolls back and exits non-zero. Nothing from the run is committed.

**Why not per-row SAVEPOINTs** (which would let earlier rows survive a DB error):
pysqlite issues `RELEASE SAVEPOINT` **without an enclosing `BEGIN`** unless the
engine adopts the documented pysqlite BEGIN recipe, so `RELEASE` auto-commits and
silently breaks `--dry-run` (rows persist despite rollback). Rather than change
the global engine's transaction handling for one feature, we abort-on-DB-error.
This is safe (no poisoned-session cascade) and honest. Revisit savepoints if the
global engine later adopts the pysqlite BEGIN recipe.

### Idempotency
Re-running the same file skips duplicates (exit 0). Skip keys mirror the `add_*`
uniqueness guards: topic `(discipline_area_id, serial_number)`, content
`(topic_id, name)`, concept `code` (global). **Limitation:** a concept `code`
reused under a *different* content is silently skipped (global code uniqueness),
not re-linked.

## Consequences / follow-ups (non-blocking)
- The engine lives under `workflow/topic/` but spans topic+content+concept — a
  cross-domain composition root in a leaf module. Consider moving to a neutral
  `workflow/importer/` and exposing `workflow import` before a second import
  surface (bib, notes) appears.
- The duplicate-resolution lookups re-implement the `add_*` uniqueness predicates
  (drift risk). Extract shared `get_topic_by_serial` / `get_content_by_name`
  helpers used by both the guard and the importer.
- Document the concept global-skip behaviour in the user-facing help/template.
