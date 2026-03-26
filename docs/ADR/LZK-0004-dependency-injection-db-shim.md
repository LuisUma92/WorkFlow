---
adr: LZK-0004
title: "Dependency Injection and ORM Shim: Peewee → SQLAlchemy Migration"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - latexzettel
  - database
  - migration
  - dependency-injection
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LZK-0000"
  - "0004"
  - "0007"
---

## Context

LaTeXZettel was originally built with Peewee ORM. The WorkFlow unification project (ADR-0004) mandated SQLAlchemy 2.0 as the single ORM. Rather than rewriting all 7 API modules (32+ database calls), a compatibility shim was created.

The API layer uses a dependency injection pattern where all functions accept a `db` module parameter. This parameter provides model classes and session management. The shim (`infra/orm.py`) re-exports SQLAlchemy models through an interface that satisfies the API's expectations.

---

## Decision

**A compatibility shim in `infra/orm.py`** that re-exports SQLAlchemy models from `workflow.db.models` and provides a lazy-initialized engine.

### Shim Architecture

```python
# infra/orm.py
import functools
from pathlib import Path
from workflow.db.engine import get_local_engine
from workflow.db.models.notes import Note, Citation, Label, Link, Tag, NoteTag

@functools.lru_cache(maxsize=1)
def get_engine():
    """Lazily create and cache the local DB engine.
    CWD must be stable before first call.
    """
    return get_local_engine(project_root=Path("."))

def create_all_tables():
    """Create LocalBase tables."""
    from workflow.db.base import LocalBase
    LocalBase.metadata.create_all(get_engine())
```

### DB Module Pattern

The `infra/db.py` module wraps database operations in a `DbModule`-compatible interface:

```python
# infra/db.py
def _get_engine(db):
    """Get engine from db module, supporting both old and new patterns."""
    if hasattr(db, "get_engine"):
        return db.get_engine()    # New: lazy function
    return db.engine              # Legacy: module attribute

@contextmanager
def db_session(db):
    """Context manager for database sessions."""
    engine = _get_engine(db)
    with Session(engine) as session:
        yield session
        session.commit()
```

### Domain Protocol

```python
# domain/types.py
@runtime_checkable
class DbModule(Protocol):
    """Contract for database module parameter."""
    Note: type
    Citation: type
    Label: type
    Link: type
    Tag: type
    def get_engine(self) -> Engine: ...
```

### Usage in API Layer

```python
# api/notes.py
def create_note(db, reference: str, filename: str) -> NoteRecord:
    with db_session(db) as session:
        note = db.Note(reference=reference, filename=filename)
        session.add(note)
        return note
```

The API never knows whether `db` is the real SQLAlchemy module, the shim, or a test mock.

---

## Architectural Rules

### MUST

- `infra/orm.py` **MUST** re-export all models from `workflow.db.models.notes`.
- `get_engine()` **MUST** use `@lru_cache` for lazy, cached initialization.
- API functions **MUST** accept `db` as their first parameter.
- `db_session()` **MUST** commit on success and rollback on exception.

### SHOULD

- `infra/db.py` **SHOULD** support both `db.get_engine()` and `db.engine` for backward compatibility.
- The shim **SHOULD** be transparent — API code should not know it exists.

### MUST NOT

- API functions **MUST NOT** import directly from `workflow.db` — always go through the `db` parameter.
- The shim **MUST NOT** add functionality beyond re-exporting — it is a pass-through.

---

## Consequences

### Benefits

- Zero API rewrites needed for Peewee → SQLAlchemy migration
- Dependency injection enables testing with mock databases
- Lazy engine avoids import-time side effects
- Backward-compatible `_get_engine` fallback

### Costs

- Extra indirection layer (shim + db parameter threading)
- `lru_cache` on `get_engine()` is CWD-dependent — fragile if CWD changes
- Two database access patterns coexist (shim vs direct `workflow.db.engine`)

### Migration Status

The shim successfully bridges Peewee → SQLAlchemy. The API layer functions correctly at runtime. ADR-0014 proposes eventually replacing the entire `latexzettel/api/` with a new `workflow.notes` module that uses SQLAlchemy directly, at which point the shim becomes unnecessary.

---

## Status

**Accepted** — documents existing shim and DI pattern

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
