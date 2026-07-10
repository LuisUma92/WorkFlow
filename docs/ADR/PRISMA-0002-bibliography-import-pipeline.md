---
id: PRISMA-0002
nav_order: 46
parent: ADRs
title: "Bibliography Import Pipeline: BibTeX Upload to Structured Data"
aliases:
  - ADR-PRISMA-0002
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - prisma
  - bibliography
  - bibtex
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "PRISMA-0000"
  - "PRISMA-0001"
---

## Context

Systematic reviews require ingesting bibliography from multiple academic databases (PubMed, Web of Science, Scopus, IEEE, ACS, APA, Google Scholar). Each database exports BibTeX with different field conventions and naming. The import pipeline must:

1. Parse BibTeX reliably despite format variations
2. Map diverse field names to a normalized schema
3. Detect and handle duplicate entries
4. Track which database sourced each article
5. Provide real-time progress feedback during batch imports

---

## Decision

**A three-stage pipeline with WebSocket progress tracking.**

### Stage 1: Upload & Parse (`addbib/`)

```
User uploads .bib file
    → bibtexparser parses entries
    → Entries stored in Django session
    → Confirmation form displays parsed entries
```

The `.bib` file is parsed using `bibtexparser` library with custom string customization. Parsed entries are stored in the Django session (not yet in the database) so the user can review before committing.

### Stage 2: Field Mapping (`prismadb/ppORM.py`)

The custom ORM translation layer handles BibTeX → Django model mapping:

| BibTeX Field  | Django Model            | Field                       | Notes                               |
| ------------- | ----------------------- | --------------------------- | ----------------------------------- |
| `author`      | `Author` + `Bib_author` | first_name, last_name, role | Split on `and`, parse "Last, First" |
| `title`       | `Bib_entries`           | title                       | Strip braces                        |
| `year`        | `Bib_entries`           | year                        | Parse to int                        |
| `journal`     | `Bib_entries`           | journal                     | Normalize abbreviations             |
| `doi`         | `Bib_entries`           | doi                         | Validate format                     |
| `abstract`    | `Abstract`              | text                        | Separate model (can be long)        |
| `keywords`    | `Keyword`               | keyword                     | Split on `;` or `,`                 |
| `url`         | `Url_list`              | url, url_type               | Classify URL type                   |
| `isbn`/`issn` | `Isn_list`              | isn_type, isn_value         | Detect type from format             |

Multi-value fields (authors, keywords, URLs) are normalized into separate junction tables.

### Stage 3: Persist with Progress (`prismadb/consumers.py`)

```
BibEntryProcessor (WebSocket consumer)
    → Iterates parsed entries
    → For each entry:
        → Check duplicates (title + year + volume)
        → Create/update Bib_entries record
        → Create Author + Bib_author records
        → Create ISN, URL, Abstract, Keyword records
        → Send progress via WebSocket channel
    → Final summary: created, updated, skipped, errors
```

Django Channels with `InMemoryChannelLayer` provides real-time progress to the browser without polling.

### Source Tracking

Each article is linked to its source database via `Referenced_databases`:

```
Referenced_databases:
    bib_entry_id → Bib_entries
    database_name: "PubMed" | "Web of Science" | "Scopus" | ...
    search_date: date
    search_query: str (the search string used)
```

This enables PRISMA flow diagrams showing how many articles came from each source and how many were duplicates.

---

## Architectural Rules

### MUST

- BibTeX parsing **MUST** use `bibtexparser` library — no hand-rolled parsers.
- Author names **MUST** be split into first_name + last_name, not stored as a single string.
- Duplicate detection **MUST** check `title + year + volume` before insert.
- Import progress **MUST** be communicated via WebSocket, not HTTP polling.

### SHOULD

- Malformed BibTeX entries **SHOULD** be skipped with a warning, not crash the import.
- The confirmation step **SHOULD** show the user what will be imported before committing.
- Source database tracking **SHOULD** record the search query and date.

### MUST NOT

- The import pipeline **MUST NOT** overwrite existing entries without user confirmation.
- Raw BibTeX strings **MUST NOT** be stored — all data must be parsed into structured fields.

---

## Consequences

### Benefits

- Handles format variations across 7+ academic databases
- Duplicate detection prevents inflated article counts
- Source tracking enables PRISMA flow diagrams
- Real-time progress for large imports (1000+ articles)

### Costs

- WebSocket infrastructure (Django Channels) for progress tracking
- Complex field mapping logic in ppORM.py (~200 lines)
- Session storage limits for very large uploads

---

## Status

**Accepted** — documents existing pipeline

---

## Change Log

| Date       | Change                                           |
| ---------- | ------------------------------------------------ |
| 2026-03-26 | Initial ADR — documents existing import pipeline |
