---
adr: "0008"
title: "SetProfiles — Author, institution, and course metadata"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - metadata
  - institution
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0006"
  - "LATEX-STY/0009"
---

## Context

Documents need author information, institutional branding (logo, name,
school), and course metadata (code, cycle, group). This data drives
headers, title pages, and exam formatting.

---

## Decision

`SetProfiles.sty` provides two layers of metadata:

### Author metadata

```latex
\author{Luis Fernando Umaña Castro}
\newcommand{\myemail}{\mailto{...}}
\let\thetitle\@title
\let\theauthor\@author
```

### Institution selectors

Commands that set `\theuni`, `\theunishort`, `\theschool`, and logos:

| Command    | Institution                         | Short  |
|------------|-------------------------------------|--------|
| `\ucr`     | Universidad de Costa Rica           | UCR    |
| `\efis`    | UCR — Escuela de Física             | UCR    |
| `\ucimed`  | Universidad de las Ciencias Médicas | UCIMED |
| `\ufide`   | Universidad Fidélitas               | UFide  |

Each command stores the university logo and school logo via `\savebox`.

### Course metadata

- `\setcourse{code}` — sets `\classcode`.
- `\setcycle{text}` — sets `\thecycle`.
- `\setgroup{number}` — sets `\thegroup`.

---

## Architectural Rules

### MUST

- Every document **MUST** call an institution selector before `\begin{document}`.
- Exam documents **MUST** also call `\setcourse`, `\setcycle`, `\setgroup`.

### SHOULD

- New institutions **SHOULD** follow the existing pattern (set `\theuni`,
  `\theunishort`, `\theschool`, save logos).

---

## Consequences

### Benefits

- Institution switch is a single command change
- Logos and names propagate to headers, title pages, and exams automatically

### Costs

- Logo paths are hardcoded relative to `\mytex`

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                        |
| ---------- | ----------------------------- |
| 2025-09-29 | Initial (UCR, Escuela Física) |
| 2026-03-20 | UCIMED, UFide added           |
