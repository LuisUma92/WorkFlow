---
adr: 0007
title: "Shared DB Module with Repository API"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - database
  - infrastructure
  - repository-pattern
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "Zettelkasten/0003"
  - "Zettelkasten/0004"
  - "Zettelkasten/0005"
---

## Context

Three subsystems maintain independent ORM models and DB logic:

- **ITEP** (`itep/database.py`): SQLAlchemy — Institution, Course, Book, Author, Topic, Content, EvaluationTemplate, Item, LectureInstance, GeneralProject
- **latexzettel** (`latexzettel/infra/orm.py`): Peewee — Note, Citation, Label, Link, Tag
- **PRISMAreview** (`prismadb/models.py`): Django ORM — Bib_entries (40+ BibLaTeX fields), Author, Abstract, PRISMA2020Checklist

Per ADR-0003 (hybrid DB) and ADR-0004 (SQLAlchemy as single ORM), all models must be unified under SQLAlchemy 2.0. The question is where they live and how consumers access them.

---

## Decision

Create a **single shared module** `src/workflow/db/` that owns all ORM models, engine management, and repository interfaces. All other modules consume it via repository Protocol interfaces.

### Module structure

```
src/workflow/db/
├── __init__.py          # Public API exports
├── base.py              # GlobalBase + LocalBase (two DeclarativeBase classes)
├── engine.py            # Engine/session factories for global and local DBs
├── models/
│   ├── __init__.py
│   ├── bibliography.py  # BibEntry, BibAuthor, Author (full BibLaTeX from PRISMAreview)
│   ├── academic.py      # Institution, MainTopic, Course, EvaluationTemplate, Item, Content, BibContent, CourseContent, CourseEvaluation
│   ├── project.py       # LectureInstance, GeneralProject, GeneralProjectBib, GeneralProjectTopic
│   ├── notes.py         # Note, Label, Link, Citation, Tag, NoteTag
│   └── exercises.py     # (Phase 4 — placeholder)
└── repos/
    ├── __init__.py
    ├── protocols.py      # Repository Protocol interfaces
    └── sqlalchemy.py     # SQLAlchemy implementations
```

### Schema unification

- **`BibEntry` replaces ITEP's `Book`**. PRISMAreview's `Bib_entries` is the canonical bibliography model with all BibLaTeX fields. ITEP's Book (name, year, edition) is a strict subset — `entry_type='book'` in BibEntry.
- **`BibAuthor` replaces both** ITEP's `BookAuthor` and PRISMAreview's `Bib_author`. Links Author to BibEntry with role (author, editor, translator).
- **`BibContent` replaces `BookContent`**. Links BibEntry to Content (chapter/section/page/exercise ranges). This is how `crete` finds exercises.
- **`Author`** is unified: one table, used by both bibliography and academic modules.
- **ITEP's `GeneralProjectBook`** becomes `GeneralProjectBib` (FK to BibEntry instead of Book).

### Two-base architecture (per ADR-0003)

- **`GlobalBase`**: bibliography, institutions, courses, topics, evaluation templates, projects → `~/.local/share/workflow/workflow.db`
- **`LocalBase`**: notes, links, labels, citations, tags, exercises, build state → `<project>/slipbox.db`

### Repository API

Protocol interfaces in `repos/protocols.py`:

- `BibRepo` — CRUD for bibliography entries, author lookup, content queries
- `ContentRepo` — chapter/section/exercise range queries (used by crete/exercise CLI)
- `NoteRepo` — note CRUD, link management, citation lookup
- `AcademicRepo` — institution, course, evaluation template queries

No module queries the ORM directly. All go through repository implementations.

---

## Architectural Rules

### MUST

- All ORM models **MUST live in `src/workflow/db/models/`**.
- `itep/database.py` **MUST be deleted** after migration; imports redirected to `workflow.db`.
- `latexzettel/infra/orm.py` **MUST be deleted** after migration; imports redirected to `workflow.db`.
- All data access **MUST go through repository interfaces**, not raw ORM queries.
- `BibEntry` **MUST preserve all BibLaTeX fields** from PRISMAreview's schema.

### SHOULD

- Repository implementations **SHOULD be the only code** that imports SQLAlchemy session/query APIs.
- Engine/session creation **SHOULD be centralized** in `workflow/db/engine.py`.

### MAY

- Alembic migrations **MAY be added** in a future phase.

---

## Implementation Notes

- Global DB path: `~/.local/share/workflow/workflow.db`
- Local DB path: `<project_root>/slipbox.db`
- Engine factory: `get_global_engine()`, `get_local_engine(project_root)`
- Session factory: `get_global_session()`, `get_local_session(project_root)`
- FK enforcement: `PRAGMA foreign_keys=ON` via SQLAlchemy event listener (existing pattern in `itep/database.py`)
- Seed data: institutions and main topics (existing in `itep/database.py`) move to `workflow/db/seed.py`

---

## Impact on AI Coding Agents

- Never create ORM models outside `src/workflow/db/models/`.
- Never query the ORM directly from CLI, API, or server code — use repositories.
- When adding new tables, decide global vs local scope per ADR-0003.

---

## Consequences

### Benefits

- Single source of truth for all data models
- Repository abstraction enables future ORM migration
- BibEntry covers full BibLaTeX spec — no information loss
- crete, latexzettel, and ITEP share the same Content/BibEntry tables

### Costs

- Significant migration effort (rewrite two ORM layers)
- All consumer modules must be updated to use repositories
- PRISMAreview needs Django adapter for shared SQLite

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
