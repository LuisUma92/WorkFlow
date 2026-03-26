---
adr: 0004
title: "SQLAlchemy 2.0 as Single ORM"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - database
  - infrastructure
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "Zettelkasten/0003"
---

## Context

Three different ORMs coexist in the WorkFlow monorepo:

- **ITEP**: SQLAlchemy 2.0 with modern `Mapped[]` annotations (most mature)
- **latexzettel**: Peewee (lightweight but divergent from ITEP)
- **PRISMAreview**: Django ORM + MariaDB (web-framework-coupled)

Maintaining three ORM stacks increases cognitive load, prevents schema sharing, and makes the hybrid DB architecture (ADR-0003) harder to implement.

---

## Decision

Adopt **SQLAlchemy 2.0** as the single ORM for all WorkFlow subsystems.

1. **Migrate latexzettel** from Peewee to SQLAlchemy, matching ITEP's `Mapped[]` conventions.
2. **PRISMAreview** keeps Django ORM for its web UI but bibliography data migrates to the shared SQLAlchemy-managed SQLite (via Django database router or thin adapter).
3. **Abstract DB access** behind a repository/interface layer so that a future ORM migration (e.g., for cloud deployment) does not require rewriting business logic.

---

## Architectural Rules

### MUST

- All new DB models **MUST use SQLAlchemy 2.0** with `Mapped[]` type annotations.
- DB access in API/domain layers **MUST go through repository interfaces**, not raw ORM queries.
- The `peewee` dependency **MUST be removed** after migration.

### SHOULD

- Repository interfaces **SHOULD be defined as Protocols** in the domain layer.
- SQLAlchemy sessions **SHOULD be managed** via context managers or dependency injection.
- Model definitions **SHOULD follow ITEP's conventions** (Base class, FK enforcement, seed data pattern).

### MAY

- SQLAlchemy **MAY be replaced** in the future if the abstraction layer is maintained.

---

## Implementation Notes

- Rewrite `src/latexzettel/infra/orm.py`: Note, Citation, Label, Link, Tag using `Mapped[]`.
- Rewrite `src/latexzettel/infra/db.py`: replace Peewee connect/close/schema_exists with SQLAlchemy engine/session (reuse `itep.database.get_engine`/`get_session`).
- Define repository Protocols in `src/latexzettel/domain/` for note CRUD, link management, citation lookup.
- Update all API modules to use repositories instead of direct ORM queries.

---

## Impact on AI Coding Agents

- Never introduce Peewee or Django ORM models outside PRISMAreview's web layer.
- All DB queries must go through repository interfaces, not raw `session.query()`.
- Follow ITEP's model conventions: `Mapped[]`, `mapped_column()`, `relationship()`.

---

## Consequences

### Benefits

- Single ORM reduces complexity and dependency count
- Schema sharing between ITEP and latexzettel becomes trivial
- Repository abstraction enables future ORM portability

### Costs

- Migration effort for latexzettel (rewrite orm.py, db.py, update API modules)
- PRISMAreview needs a DB router or adapter for shared data

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
