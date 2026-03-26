---
adr: PRISMA-0001
title: "Dual-Database Router: MariaDB + Shared SQLite"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - prisma
  - database
  - django
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "PRISMA-0000"
  - "0003"
  - "0007"
---

## Context

PRISMAreview needs to read bibliography data managed by WorkFlow's SQLAlchemy-based system. Two approaches were considered:

1. **API bridge** — PRISMAreview calls a REST/RPC API to query bibliography data
2. **Direct database sharing** — PRISMAreview reads the same SQLite file via a Django database router

The API approach adds network overhead and a service dependency. Direct database sharing is simpler for a single-user academic toolkit.

---

## Decision

**Use a Django database router** (`shared_db/router.py`) that directs read queries for bibliography models to the shared `workflow.db` SQLite file.

### Router Implementation

```python
class SharedDbRouter:
    """Route bibliography reads to shared SQLite, writes to MariaDB."""

    SHARED_MODELS = {
        "bib_entries", "author", "bib_author", "isn_list",
        "referenced_databases", "url_list", "abstract", "keyword",
    }

    def db_for_read(self, model, **hints):
        if model._meta.db_table in self.SHARED_MODELS:
            return "shared"
        return "default"

    def db_for_write(self, model, **hints):
        if model._meta.db_table in self.SHARED_MODELS:
            return None  # Prevent writes to shared DB
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True  # Allow cross-DB relations in memory

    def allow_migrate(self, db, app_label, **hints):
        if db == "shared":
            return False  # Never migrate shared DB
        return True
```

### Database Configuration (settings.py)

```python
DATABASES = {
    "default": {
        "ENGINE": "mysql.connector.django",
        "NAME": "prisma",
        "HOST": "localhost",
        "PORT": "3306",
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
    },
    "shared": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get(
            "WORKFLOW_DB_PATH",
            str(Path(user_data_dir("workflow", "LuisUmana")) / "workflow.db"),
        ),
    },
}

DATABASE_ROUTERS = ["shared_db.router.SharedDbRouter"]
```

### Shared Models

These 8 Django models mirror the SQLAlchemy models in `workflow.db.models.bibliography`:

| Django Model | SQLAlchemy Model | Table | Shared Fields |
|-------------|-----------------|-------|---------------|
| `Bib_entries` | `BibEntry` | `bib_entry` | bibkey, title, year, journal, volume, etc. |
| `Author` | `BibAuthor` | `bib_author` | first_name, last_name |
| `Bib_author` | — | `bib_entry_author` | bib_entry_id, author_id, role |
| `Isn_list` | — | `bib_isn` | isn_type, isn_value |
| `Referenced_databases` | — | `bib_source` | database_name, search_date |
| `Url_list` | `BibUrl` | `bib_url` | url, url_type |
| `Abstract` | — | `bib_abstract` | text, language |
| `Keyword` | — | `bib_keyword` | keyword |

---

## Architectural Rules

### MUST

- `SharedDbRouter.db_for_write` **MUST** return `None` for shared models — enforcing read-only access.
- `allow_migrate` **MUST** return `False` for the `shared` database — Django must never alter WorkFlow's schema.
- The `shared` database path **MUST** resolve to the same file as `workflow.db.engine.get_global_engine()`.
- `DATABASE_ROUTERS` **MUST** be configured in settings.py for the router to activate.

### SHOULD

- Shared model field names **SHOULD** align with SQLAlchemy model column names to avoid confusion.
- The router **SHOULD** be tested with a mock shared DB to verify read-only enforcement.

### MUST NOT

- Django migrations **MUST NOT** target the `shared` database.
- PRISMAreview **MUST NOT** create, update, or delete records in shared tables.

---

## Implementation Notes

**Current gap**: `DATABASE_ROUTERS` is not yet configured in `settings.py`. The `shared_db/README.md` documents the required configuration but it has not been applied. The router code exists and is correct — it just needs to be wired in settings.

**Migration path**: When PRISMAreview migrates from MariaDB to SQLite (per project roadmap), the router simplifies — both databases become SQLite, and the router only separates read/write concerns.

---

## Consequences

### Benefits

- Zero-overhead data sharing (direct file access)
- No API service to maintain
- Django's ORM handles cross-DB joins in memory
- Read-only enforcement prevents accidental data corruption

### Costs

- Two ORM systems (Django + SQLAlchemy) model the same tables
- Schema drift risk if either side changes column names
- File locking: concurrent SQLite writes from WorkFlow CLI + Django reads could conflict (mitigated: Django only reads)

---

## Status

**Accepted** — documents existing design (router code exists, needs wiring)

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR — documents existing router design |
