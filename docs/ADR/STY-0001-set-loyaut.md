---
adr: "0001"
title: "SetLoyaut — Page geometry and spacing"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - layout
  - geometry
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "STY-0011"
---

## Context

Documents across projects need consistent page dimensions, margins, and
paragraph spacing. Two layout modes are needed: full-page documents and
standalone slides.

---

## Decision

Two layout files:

### SetLoyaut.sty — Full-page documents

```latex
\geometry{
  letterpaper,
  top=15mm, bottom=15mm,
  left=25mm, right=25mm,
  includeheadfoot=true,
  footskip=10mm, headheight=7mm, headsep=3mm
}
\setlength{\parskip}{1.3em}
```

### SetLoyaut-StandAlone.sty — Standalone slides

```latex
\geometry{
  paperwidth=16.5cm, paperheight=15.5cm,
  left=15mm, right=15mm,
  top=10mm, bottom=15mm,
  includeheadfoot=false
}
\AtBeginDocument{\fontsize{16}{19}\selectfont}
\setlength{\parindent}{0pt}
```

---

## Architectural Rules

### MUST

- Full documents **MUST** symlink `1-loyaut.sty` to `SetLoyaut.sty`.
- StandAlone mode **MUST** use `SetLoyaut-StandAlone.sty` for slide-sized output.

### SHOULD

- Paragraph spacing **SHOULD** remain at `1.3em` (one-and-a-half) unless overridden.

---

## Consequences

### Benefits

- Uniform page dimensions across all projects
- Standalone mode enables slide-like output without Beamer

### Costs

- Standalone geometry is fixed (16.5 x 15.5 cm), not parameterized

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                           |
| ---------- | -------------------------------- |
| 2025-09-29 | Initial version (SetLoyaut.sty)  |
| 2026-03-20 | StandAlone variant added         |
