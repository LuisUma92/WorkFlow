---
adr: PRISMA-0004
title: "PRISMAreview Data Model: 30+ Django Models for Systematic Review"
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
  - data-model
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "PRISMA-0000"
  - "PRISMA-0001"
  - "PRISMA-0002"
  - "PRISMA-0003"
---

## Context

A PRISMA systematic review requires tracking articles through a multi-stage pipeline: identification, screening, eligibility, and inclusion. The data model must capture:

- Full BibLaTeX metadata (40+ fields per article)
- Multi-value fields (multiple authors, keywords, URLs per article)
- Source tracking (which database found each article)
- Review decisions with rationale
- PRISMA 2020 checklist compliance

---

## Decision

**30+ Django models organized in 4 layers**, mirroring the PRISMA pipeline stages.

### Layer 1: Bibliography Core

```
Bib_entries (central entity)
    ├── bibkey: str (unique BibTeX key)
    ├── entry_type: str (article, book, inproceedings, ...)
    ├── title: str
    ├── year: int
    ├── journal: str
    ├── volume: str
    ├── pages: str
    ├── doi: str
    ├── publisher: str
    ├── booktitle: str
    ├── note: str
    ├── language: str
    ├── ... (40+ BibLaTeX fields)
    └── unique_together: (title, year, volume)

Author
    ├── first_name: str
    ├── last_name: str
    └── unique_together: (first_name, last_name)

Bib_author (junction)
    ├── bib_entry_id → Bib_entries
    ├── author_id → Author
    └── role: str (author, editor, translator)
```

### Layer 2: Metadata Extensions

```
Isn_list
    ├── bib_entry_id → Bib_entries
    ├── isn_type: str (ISBN, ISSN, eISSN)
    └── isn_value: str

Url_list
    ├── bib_entry_id → Bib_entries
    ├── url: str
    └── url_type: str (DOI, publisher, preprint, ...)

Abstract
    ├── bib_entry_id → Bib_entries
    ├── text: TextField
    └── language: str

Referenced_databases
    ├── bib_entry_id → Bib_entries
    ├── database_name: str (PubMed, WoS, Scopus, ...)
    ├── search_date: date
    └── search_query: str
```

### Layer 3: Review & Screening

```
Keyword
    ├── keyword: str (unique)
    └── articles: M2M → Bib_entries (via Bib_keyword)

Reviewed
    ├── bib_entry_id → Bib_entries
    ├── keyword_id → Keyword
    ├── included: bool
    └── review_date: datetime

Rationale_list
    ├── text: str
    └── rationale_type: str (inclusion | exclusion)

Review_rationale (junction)
    ├── reviewed_id → Reviewed
    └── rationale_id → Rationale_list

Tags
    ├── name: str
    └── tag_type: str

Article_tags (junction)
    ├── bib_entry_id → Bib_entries
    └── tag_id → Tags
```

### Layer 4: PRISMA Compliance

```
PRISMA2020Checklist
    ├── item_number: int (1-27)
    ├── section: str (Title, Abstract, Introduction, Methods, ...)
    ├── item_description: str
    ├── completed: bool
    └── notes: TextField
```

### Supported Academic Databases

The `Referenced_databases` model tracks articles from:

| Database | Field | Notes |
|----------|-------|-------|
| PubMed | PMID | Medical/biomedical |
| Web of Science | WoS ID | Multidisciplinary |
| Scopus | Scopus ID | Multidisciplinary |
| IEEE Xplore | IEEE ID | Engineering/CS |
| ACS Publications | ACS DOI | Chemistry |
| APA PsycINFO | PsycINFO ID | Psychology |
| Google Scholar | — | Broad discovery |

### Duplicate Detection

Uniqueness constraints prevent duplicate entries:

```python
class Bib_entries(models.Model):
    class Meta:
        unique_together = [("title", "year", "volume")]
```

When a duplicate is detected during import, the existing record is updated with any new metadata (e.g., additional source database).

---

## Architectural Rules

### MUST

- `Bib_entries` **MUST** enforce uniqueness on `(title, year, volume)`.
- Authors **MUST** be stored in a normalized junction table, not as a single string field.
- Every `Reviewed` record **MUST** reference both the article AND the keyword under which it was screened.
- Source databases **MUST** be tracked per article for PRISMA flow diagram generation.

### SHOULD

- Abstract text **SHOULD** be stored in a separate model (can be very large).
- ISBNs and ISSNs **SHOULD** be normalized and validated on import.
- The PRISMA 2020 checklist **SHOULD** cover all 27 items.

### MUST NOT

- BibTeX raw strings **MUST NOT** be stored as-is — all fields must be parsed into structured columns.
- Author names **MUST NOT** be stored as a concatenated string — use the junction table.

---

## Consequences

### Benefits

- Full BibLaTeX coverage (40+ fields) handles any article type
- Normalized junction tables enable proper querying (find all articles by author X)
- Source tracking supports PRISMA flow diagram generation
- PRISMA 2020 checklist ensures reporting compliance

### Costs

- 30+ models is a large schema for a single app
- Junction tables add complexity for simple queries
- Two author models exist: `Bib_author` in PRISMAreview and `BibAuthor` in `workflow.db` — schema drift risk

---

## Status

**Accepted** — documents existing data model

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR — documents existing data model |
