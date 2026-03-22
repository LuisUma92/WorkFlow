---
adr: "0009"
title: "SetHeaders — Page styles per document type"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - fancyhdr
  - headers
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0001"
  - "LATEX-STY/0008"
  - "LATEX-STY/0003"
---

## Context

Different document types (homework, lecture notes, exams) need distinct
header/footer layouts. Exam headers also vary by institution (UCR shows
different info than UCIMED).

---

## Decision

`SetHeaders.sty` defines multiple `\fancypagestyle` entries using `fancyhdr`.

### Page styles

| Style          | Use case        | Header                          | Footer       |
|----------------|-----------------|---------------------------------|--------------|
| `homework`     | Homework/notes  | Lecture name (R), author (L)    | Page number  |
| `pres`         | Front matter    | Empty                           | Roman page   |
| `plainPres`    | Plain front     | Empty                           | Page number  |
| `cuerpo`       | Body            | Page number (R odd, L even)     | Empty        |
| `plainCuerpo`  | Plain body      | Page number (R odd, L even)     | Empty        |
| `uplain`       | Exams           | Institution-specific (below)    | Exam metadata|

### Institution-specific exam headers (`uplain`)

- **UCIMED**: "Página X/Y" (right), exam+course+cycle (left footer).
- **UCR**: Group (right), author (left), page (center footer).
- **UFide**: Course code (left), cycle (right), page (center footer).

The dispatch uses `\ifthenelse{\equal{\theunishort}{...}}`.

---

## Architectural Rules

### MUST

- `\pagestyle` **MUST** be set to one of the styles defined here.
- Exam documents **MUST** use `uplain` style.

### MUST NOT

- Documents **MUST NOT** define inline `\fancyhead`/`\fancyfoot` overrides.

### SHOULD

- New document types **SHOULD** get a named `\fancypagestyle`.

---

## Consequences

### Benefits

- Institution-aware exam headers with zero per-document configuration
- Consistent pagination across document types

### Costs

- Institution dispatch via string comparison (not extensible)

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                           |
| ---------- | -------------------------------- |
| 2025-09-29 | Initial (homework, pres, cuerpo) |
| 2026-03-20 | uplain with institution dispatch |
