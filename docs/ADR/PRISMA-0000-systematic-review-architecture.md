---
adr: PRISMA-0000
title: "PRISMAreview Systematic Review Architecture"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - prisma
  - django
  - systematic-review
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "0003"
  - "0004"
  - "0007"
---

## Context

Systematic literature reviews following the PRISMA 2020 methodology require:

1. **Bibliography ingestion** — importing articles from multiple databases (PubMed, Web of Science, Scopus, IEEE, ACS, APA, Google Scholar)
2. **Duplicate detection** — identifying and merging duplicate entries across databases
3. **Screening** — iterating through articles, assessing inclusion/exclusion with rationale
4. **Keyword management** — tagging articles with controlled vocabulary
5. **Progress tracking** — real-time feedback during batch imports

A web-based interface is needed because screening involves reading abstracts and making quick inclusion decisions — a workflow better suited to a browser than a CLI.

---

## Decision

**PRISMAreview is a standalone Django 5.0 web application** within the WorkFlow monorepo. It manages its own review metadata while reading shared bibliography data from the WorkFlow global database.

### Architecture

```
PRISMAreview (Django)
├── pprsite/          # Django project config (ASGI, settings, URLs)
├── prismadb/         # Core: 30+ Django models, WebSocket consumers, ORM parser
├── addbib/           # Bibliography import workflow (BibTeX upload → parse → confirm)
├── review/           # Article review workflow (keyword → screen → tag)
├── shared_db/        # Database router for reading from workflow.db
├── home/             # Landing page
└── inspectdatabase/  # Admin inspection tools
```

### Dual-Database Design

| Database | Engine | Purpose | Access |
|----------|--------|---------|--------|
| `prisma` (default) | MariaDB | Review metadata: keywords, rationales, tags, inclusion decisions | Read/Write |
| `shared` | SQLite (workflow.db) | Bibliography: articles, authors, ISBNs, URLs, abstracts | Read-only |

The separation ensures:
- WorkFlow CLI tools can write bibliography data without Django dependency
- PRISMAreview can read bibliography without owning the data
- Review metadata stays in MariaDB (Django's native backend)

### Key Components

**Bibliography Import Pipeline** (`addbib/`):
1. User uploads `.bib` file via web form
2. `bibtexparser` parses BibTeX entries
3. Entries stored in Django session for confirmation
4. `BibEntryProcessor` (WebSocket consumer) saves confirmed entries to DB
5. Real-time progress via Django Channels (`InMemoryChannelLayer`)

**Review Workflow** (`review/`):
1. Select keyword to screen articles against
2. Iterate through matching articles showing title + abstract
3. User marks inclusion/exclusion with rationale
4. Tags assigned for classification
5. Progress tracked in `Reviewed` model

**Custom ORM Layer** (`prismadb/ppORM.py`):
- Translates BibTeX field names to Django model fields
- Handles multi-value fields (authors, keywords, URLs)
- Manages database-source tracking (which search engine found each article)

---

## Architectural Rules

### MUST

- PRISMAreview **MUST** remain a standalone Django app — no imports from `workflow.*` Python modules.
- Bibliography data **MUST** be read-only from PRISMAreview's perspective — writes go through WorkFlow CLI.
- The `SharedDbRouter` **MUST** enforce read-only access to shared tables via `db_for_write` returning `None`.
- WebSocket consumers **MUST** use Django Channels for real-time import progress.

### SHOULD

- Review decisions (inclusion/exclusion) **SHOULD** be stored with rationale text and reviewer ID.
- Duplicate detection **SHOULD** check `title + year + volume` uniqueness.
- The `.bib` parser **SHOULD** handle malformed BibTeX entries gracefully.

### MUST NOT

- PRISMAreview **MUST NOT** write to the shared SQLite database.
- Django models **MUST NOT** duplicate the SQLAlchemy model definitions in `workflow.db.models`.
- The web UI **MUST NOT** expose raw database queries or admin panels in production.

---

## Consequences

### Benefits

- Web-based screening is faster than CLI for abstract review
- Dual-database separates concerns cleanly
- Django ecosystem provides authentication, admin, forms
- WebSocket enables real-time import feedback

### Costs

- MariaDB dependency (separate from SQLite-based WorkFlow)
- Django is a heavy dependency for what is otherwise a CLI toolkit
- Two ORM systems (Django ORM + SQLAlchemy) coexist in the monorepo
- No unit tests exist for PRISMAreview

---

## Status

**Accepted** — documents existing architecture

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR — documents existing system |
