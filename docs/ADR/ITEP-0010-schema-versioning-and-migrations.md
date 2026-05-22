---
id: ITEP-0010
title: "Schema versioning and forward-only migrations for GlobalBase + LocalBase"
aliases:
  - ADR-ITEP-0010
status: Implemented
date: 2026-04-29
authors:
  - Luis Umaña
reviewers: []
tags:
  - database
  - migrations
  - infrastructure
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - 0003-hybrid-database
  - 0004-sqlalchemy-single-orm
  - 0007-shared-db-module
  - ITEP-0001-sqlalchemy-persistence
  - ITEP-0008-general-project-nomenclature
---

## Context

`workflow.db` initialises every database with `Base.metadata.create_all`
(`init_global_db`, `init_local_db` in `src/workflow/db/engine.py`). There is
no schema-version table, no migration log, and no generic runner. Consequences
already observed in production:

- `workflow evaluations list` crashes with
  `sqlite3.OperationalError: no such column: evaluation_template.description`
  on any DB that pre-dates a model edit (request
  `tasks/requests/2026-04-29-evaluations-schema-migration.md`).
- ITEP-0008 shipped its migration as a one-off Click subcommand
  (`workflow db migrate itep-0008`) coupled to a single-user data fix-up
  flag (`--backfill-nuclear-physics`). There is no extension point for the
  next migration.
- ITEP-0008's catalog/state separation lacks a hard FK from `MainTopic`
  to `DisciplineArea`: state rows can drift away from the catalog. This
  ADR ships the migration that closes the gap.
- Eight live `slipbox.db` files (`LocalBase`) exist across `~/Projects/`
  and `~/Documents/01-U/`; any future `Note`/`Citation`/`Link` column
  edit has the same crash surface as the global case.

The user's live `~/.local/share/workflow/workflow.db` was manually walked
through Phase 0 on 2026-04-29: ITEP-0008 schema migration applied,
discipline codes seeded (233 rows), stale `main_topic` (14 rows) and
`general_project` (1 row) wiped to a clean baseline. The DB is now
**ITEP-0008-clean** but pre-FK and pre-`evaluation_template.description`.

A decision is required **now** because the next open requests
(`exercise register`, `course add-practice`) both add columns that will
reproduce the same crash on every live DB unless versioning lands first.

---

## Decision Drivers

- maintainability — single, predictable upgrade path for both bases
- operational reliability — `OperationalError` must become an actionable
  CLI message, never a Python traceback to the end user
- simplicity — no Alembic; the project has one developer, two bases, and
  no autogenerate need
- forward compatibility — must support both `GlobalBase` and `LocalBase`
  with independent revision histories
- testability — migrations must be exercised by `pytest` against a
  throw-away SQLite, not against a live DB

---

## Decision

Introduce **forward-only, numbered migrations** with a `schema_version`
table per base, discovered from the filesystem and applied in lexical
order. The runner is exposed as `workflow db migrate`.

### Migration module shape

Each migration is a Python module:

```python
# src/workflow/db/migrations/global/0003_evaluation_template_description.py
from sqlalchemy.engine import Connection

revision: str = "0003_evaluation_template_description"
description: str = "Add description column to evaluation_template."
base: str = "global"  # or "local"


def upgrade(connection: Connection) -> None:
    connection.exec_driver_sql(
        "ALTER TABLE evaluation_template ADD COLUMN description TEXT NULL"
    )
```

No `downgrade`. Forward-only.

### Schema version table

A single table, identical shape on both bases:

```python
class SchemaVersion(<Base>):
    __tablename__ = "schema_version"
    revision: Mapped[str] = mapped_column(String(128), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

`init_global_db` / `init_local_db` are extended to:

1. create the `schema_version` table first,
2. apply every pending migration discovered for that base,
3. only then call `Base.metadata.create_all` for any net-new tables.

Fresh DBs are stamped at the latest revision (no migrations re-run).

### CLI

```
workflow db migrate           [--base global|local|all] [--to REV] [--dry-run] [--json]
workflow db migrate status    [--base global|local|all] [--json]
```

The legacy `workflow db migrate itep-0008` Click subcommand is **removed**
in the same release that lands ITEP-0010. Phase 0 manual migration on
2026-04-29 already brought the only known live DB to an ITEP-0008-clean
baseline, so no deprecation alias is required.

### Error translation

`src/workflow/db/errors.py` defines `SchemaOutOfDateError` and a regex
translator that recognises `no such column: T.C` and `no such table: T`.
A small decorator (`@with_schema_guard`) wraps Click commands that hit
the DB; on `OperationalError` it raises
`click.ClickException("Database schema is out of date (missing: …). "
"Run: workflow db migrate")` — exit 1, no traceback.

---

## Architectural Rules

### MUST

- Every schema change to a `GlobalBase` or `LocalBase` model **MUST** ship
  with a corresponding migration module under
  `src/workflow/db/migrations/{global,local}/NNNN_slug.py`.
- Migrations **MUST** be forward-only. No `downgrade`. No edits to a
  migration once committed; introduce a follow-up revision instead.
- Migration files **MUST** expose `revision: str`, `description: str`,
  `base: Literal["global","local"]`, and `def upgrade(connection)`.
- `revision` values **MUST** be lexically sortable
  (`NNNN_slug`, four-digit zero-padded counter).
- `init_global_db` / `init_local_db` **MUST** be the only call sites that
  apply migrations during normal program flow; CLI invocation is the only
  other entry point.
- Any Click command that opens a session against `workflow.db` or a
  project `slipbox.db` **MUST** be wrapped with `@with_schema_guard`.
- The `schema_version` table **MUST NOT** be modified by migrations
  themselves; only the runner writes to it.

### SHOULD

- Migration filenames **SHOULD** reference the ADR that introduced them
  when applicable (e.g. `0002_itep_0008_general_project_nomenclature.py`).
- Tests for new migrations **SHOULD** assert idempotency: applying twice
  produces no further changes.
- Migration `upgrade()` bodies **SHOULD** prefer `connection.exec_driver_sql`
  over ORM-level operations, so they remain stable as models drift.

### MAY

- A migration **MAY** call ORM helpers when seeding reference data is
  cheaper than raw SQL, provided it imports models lazily inside the
  function body.
- A migration **MAY** be split across multiple files when its logical
  unit needs ordering (e.g. `0007a_create_table.py`, `0007b_seed.py`).

---

## Implementation Notes

Layout:

```
src/workflow/db/
├── engine.py            # init_global_db / init_local_db now run migrations
├── errors.py            # NEW: SchemaOutOfDateError, translate_operational_error
├── schema_version.py    # NEW: SchemaVersion model + helpers
└── migrations/
    ├── __init__.py      # discovery + runner
    ├── global/
    │   ├── 0001_baseline.py                        # stamps current ITEP-0008-clean schema
    │   ├── 0002_main_topic_discipline_area_fk.py   # ITEP-0008 amendment (Phase 1B)
    │   └── 0003_evaluation_template_description.py # fixes evaluations list crash
    └── local/
        └── 0001_baseline.py
```

Migration ordering is deliberate: **structure first, columns second.**
`0002` normalises the catalog/state link before `0003` papers over the
`description` crash, so that any future query against `evaluation_template`
runs on top of an already-correct `main_topic` shape.

Existing `src/workflow/db/migrations/itep_0008.py`, the
`migrate_itep_0008` Click subcommand, and the
`--backfill-nuclear-physics` flag are **deleted** in the same release
that ships ITEP-0010. Phase 0 already brought the live DB past that
work; no other DB is known to need it. This is the only ADR-sanctioned
deletion of migration code in the project's history — future migrations
**MUST NOT** be deleted once merged.

Tests live under:

```
tests/workflow/db/
├── test_schema_version.py
├── test_migration_runner.py
├── test_migrate_cli.py
└── test_schema_guard.py
```

Test plan:

- discovery returns migrations in lexical order, separately per base
- fresh `init_global_db` stamps head and runs zero migrations
- pre-existing baseline DB applies every migration in order
- second `migrate` invocation is a no-op (idempotent)
- `--dry-run` prints SQL without modifying the DB
- `--json` shape: `{"applied": [...], "skipped": [...], "head": "0003_…"}`
- `@with_schema_guard` translates `OperationalError(no such column: T.C)`
  into `ClickException` with substring `workflow db migrate`
- deprecated alias still applies the same migration once and warns

---

## Impact on AI Coding Agents

Agents modifying `workflow.db` models must:

- Add a migration file under `migrations/{global,local}/NNNN_slug.py` in
  the same commit as the model edit. PRs that change a model without a
  migration **MUST** be rejected by review.
- Never edit a migration that has already been merged. Add a new revision
  on top.
- Wrap any new Click command that opens a session with
  `@with_schema_guard`. Untrapped `OperationalError` is a regression.
- Treat `init_global_db` / `init_local_db` as the **only** sanctioned way
  to bootstrap a DB in tests and scripts; do not call
  `Base.metadata.create_all` directly outside `engine.py`.

---

## Consequences

### Benefits

- predictable upgrade path for the user's live DBs (one global + 8 local)
- friendly error message instead of a SQL traceback whenever a model
  drifts ahead of an installed DB
- ITEP-0008 migration becomes a normal entry in the log; future ADRs
  ship the same way without bespoke CLI subcommands
- migrations are runnable in CI against tmp DBs, decoupled from the
  user's live data

### Costs

- one extra file per model schema change
- additional discipline at PR review time
- migration history becomes a permanent archive (cannot rewrite)

---

## Alternatives Considered

### Alternative A — Adopt Alembic

#### Advantages

- industry standard, mature, supports autogenerate

#### Disadvantages

- two `MetaData` objects (`GlobalBase`, `LocalBase`) require two Alembic
  envs and two `alembic.ini` files; high configuration overhead for a
  single-developer project
- autogenerate is unreliable on column-type changes and SQLite-specific
  ALTER limitations; we would still hand-write most migrations
- introduces an external CLI (`alembic upgrade head`) that conflicts with
  the project rule that `workflow` is the single entry point

Rejected: cost outweighs benefit at current scale. Revisit if team > 1
or if `LocalBase` ships to non-developer end users.

### Alternative B — Drop the column / change the model to match the live DB

#### Advantages

- zero new infrastructure

#### Disadvantages

- only fixes the current crash; the next column add reproduces it
- regresses ADR-0016 (`evaluation_template.description` is part of the
  evaluation CLI contract)

Rejected.

### Alternative C — Per-ADR ad-hoc Click subcommand (status quo)

#### Advantages

- no abstraction needed

#### Disadvantages

- already producing the `--backfill-nuclear-physics` anti-pattern
- no `schema_version` means `migrate itep-0008` cannot tell whether it
  has run before
- end-user error remains a SQL traceback

Rejected.

---

## Compatibility / Migration

Backwards-compatible for fresh installs. For the user's live DBs:

1. **Global DB** (`~/.local/share/workflow/workflow.db`): already
   ITEP-0008-clean (Phase 0, 2026-04-29). On first `workflow db migrate`
   after this ADR lands, the runner stamps `0001_baseline`, then applies
   `0002_main_topic_discipline_area_fk` (no rows to backfill — table
   empty) and `0003_evaluation_template_description`.
2. **Local DBs** (`slipbox.db` × 8): on next `workflow notes` or
   `workflow lecture` invocation, `init_local_db` stamps baseline. No
   data migration required at this point (no LocalBase column has
   shifted yet).
3. **`migrate_itep_0008` removal**: deleted in the same release. No
   alias period. Phase 0 was the one-and-only invocation of that path.

---

## References

- ADR-0007 (shared DB module + repository API)
- ADR-0003 (hybrid global/local DB)
- ITEP-0008 (general-project nomenclature; first real schema migration)
- `tasks/requests/2026-04-29-evaluations-schema-migration.md`
- Martin Fowler — _Evolutionary Database Design_
- Alembic docs — _why we considered and rejected it for now_

---

## Status

**Accepted** (2026-04-29).

Promotes to **Implemented (partial)** when Phases A + B + C land on
master.

Promotes to **Implemented** when:

- the live global DB has applied through `0003`,
- `slipbox.db` baseline stamped on every active project,
- `tasks/requests/2026-04-29-evaluations-schema-migration.md` is closed
  with `closed_by: ITEP-0010`.

---

## Change Log

| Date       | Change                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------- |
| 2026-04-29 | Initial draft (Proposed); awaiting user review.                                                    |
| 2026-04-29 | Accepted after Phase 0 manual migration; FK migration reordered to ship before description column. |
