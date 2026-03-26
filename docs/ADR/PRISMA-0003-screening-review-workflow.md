---
adr: PRISMA-0003
title: "Article Screening and Review Workflow"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - prisma
  - systematic-review
  - screening
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "PRISMA-0000"
  - "PRISMA-0002"
---

## Context

After bibliography import, the PRISMA systematic review process requires:

1. **Title/abstract screening** — quickly include/exclude articles based on relevance
2. **Rationale recording** — documenting why each article was included or excluded
3. **Keyword-based filtering** — reviewing articles grouped by topic keywords
4. **Tagging** — classifying included articles for analysis
5. **PRISMA checklist** — tracking compliance with PRISMA 2020 guidelines

The screening process is iterative — articles may be re-reviewed as inclusion criteria evolve.

---

## Decision

**A keyword-driven screening workflow in the Django web UI** with structured inclusion/exclusion tracking.

### Data Model

```
Reviewed
    bib_entry_id → Bib_entries
    keyword_id → Keyword
    included: bool
    review_date: datetime

Review_rationale
    reviewed_id → Reviewed
    rationale_id → Rationale_list

Rationale_list
    text: str           # e.g., "Not peer-reviewed", "Wrong population"
    rationale_type: str  # "inclusion" | "exclusion"

Article_tags
    bib_entry_id → Bib_entries
    tag_id → Tags

Tags
    name: str
    tag_type: str

PRISMA2020Checklist
    item_number: int
    item_description: str
    completed: bool
    notes: str
```

### Screening Flow

```
1. Select keyword to screen
    → Query articles matching keyword
    → Display article list with title, year, journal

2. For each article:
    → Show title + abstract
    → User decides: Include / Exclude
    → If excluding: select rationale(s) from predefined list
    → If including: assign tags for classification
    → Decision saved to Reviewed table

3. Progress dashboard:
    → Articles screened vs remaining
    → Inclusion/exclusion counts per keyword
    → PRISMA flow diagram data
```

### Review States

An article can be in one of these states relative to a keyword:

| State | Reviewed Record | Included |
|-------|----------------|----------|
| Unscreened | No record | — |
| Included | Yes | True |
| Excluded | Yes | False |
| Re-review needed | Marked for re-assessment | — |

### Rationale System

Predefined rationales ensure consistency:

**Exclusion rationales**: "Not peer-reviewed", "Wrong population", "Wrong intervention", "Duplicate", "Language barrier", "Retracted", "Conference abstract only", "Protocol/registration only"

**Inclusion rationales**: "Directly relevant", "Background/context", "Methodology reference", "Data source"

Custom rationales can be added per review.

---

## Architectural Rules

### MUST

- Every exclusion **MUST** have at least one rationale — no unexplained exclusions.
- Screening decisions **MUST** be recorded with timestamp and keyword context.
- The `Reviewed` model **MUST** track the keyword-article pair, not just the article — an article may be reviewed under multiple keywords.

### SHOULD

- The screening UI **SHOULD** show article abstract inline to avoid context-switching.
- Rationale lists **SHOULD** be configurable per review project.
- Inclusion/exclusion counts **SHOULD** be available for PRISMA flow diagram generation.

### MUST NOT

- Screening **MUST NOT** delete bibliography entries — only mark inclusion/exclusion.
- Rationale text **MUST NOT** be free-form only — use predefined lists for consistency, with optional notes.

---

## Consequences

### Benefits

- Structured rationale recording meets PRISMA 2020 reporting requirements
- Keyword-based grouping enables focused screening sessions
- Review data supports automatic PRISMA flow diagram generation
- Re-review capability accommodates evolving criteria

### Costs

- Keyword-article junction adds complexity vs simple article-level screening
- Predefined rationale lists require initial setup per review
- Web-based screening requires Django server running

---

## Status

**Accepted** — documents existing workflow

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR — documents existing screening workflow |
