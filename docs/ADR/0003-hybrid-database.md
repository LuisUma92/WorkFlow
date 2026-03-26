---
adr: 0003
title: "Hybrid Database Architecture (Global + Local)"
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
  - "Zettelkasten/0004"
  - "ITEP/0003"
---

## Context

The WorkFlow system has three subsystems with independent databases:

- **ITEP**: SQLAlchemy + SQLite (`~/.config/itep/itep.db`) — institutions, courses, books, topics, evaluations
- **latexzettel**: Peewee + SQLite (`slipbox.db` per project) — notes, links, citations, labels, tags
- **PRISMAreview**: Django ORM + MariaDB — bibliography, PRISMA checklists, abstracts

Each ITEP project (lecture instance, general project) represents a structured output of the Zettelkasten — a paper, presentation, report, or course. Projects need both shared reference data and project-specific content.

A decision is required on how to unify data access while preserving the project-scoped nature of notes and exercises.

---

## Decision

Adopt a **hybrid database model** with two tiers:

### Global Database (`~/.local/share/workflow/workflow.db`)

Contains reference data shared across all projects:

- ITEP reference data: Institution, MainTopic, Author, Book, Content, Course, EvaluationTemplate, Item
- Bibliography: BibEntry, BibAuthor, BibKeyword, BibUrl, BibAbstract (promoted from PRISMAreview)
- Base Zettelkasten structure: permanent notes, literature notes, concept registry

### Local Database (per ITEP project)

Contains project-specific data:

- Notes and links specific to the project scope
- Exercises assigned to the project
- Build state (render timestamps, TikZ compilation hashes)
- Project-specific tags and metadata

### Inheritance

Local databases **inherit** relevant knowledge relations from the global DB. When a project references a global concept, note, or citation, the relation is stored locally to enable offline/independent operation.

---

## Architectural Rules

### MUST

- Reference data (institutions, books, authors, topics) **MUST live in the global DB only**.
- Notes specific to a project **MUST live in the project's local DB**.
- Bibliography entries **MUST be global** — all projects share the same citation pool.
- The CLI **MUST connect to both DBs** when operating within a project context.

### SHOULD

- Projects **SHOULD be able to operate** with only their local DB for basic tasks (render, sync).
- Global-to-local sync **SHOULD be explicit** (CLI command), not implicit.

### MAY

- A future `workflow sync` command **MAY propagate** global updates to local DBs.

---

## Implementation Notes

- Global DB path: `~/.local/share/workflow/workflow.db` (resolved via `appdirs` or hardcoded default).
- Local DB path: `<project_root>/slipbox.db` (existing latexzettel convention).
- Both use SQLAlchemy with the same `Base` and model definitions.
- The CLI accepts `--root` to identify the project and `--global-db` to locate the global DB.
- ITEP's existing `DB_PATH` in `itep/defaults.py` migrates to the global path.

---

## Impact on AI Coding Agents

- Always check whether data belongs in global or local scope before writing.
- Reference data mutations (new book, new institution) go to global DB.
- Note/exercise mutations go to local DB.
- Never duplicate reference data in local DBs.

---

## Consequences

### Benefits

- Clean separation between shared knowledge and project-specific work
- Projects remain portable (local DB is self-contained for basic ops)
- Single source of truth for bibliography and reference data

### Costs

- Two-DB connection management adds complexity
- Sync between global and local requires explicit design
- Migration from current three separate DB stacks

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
