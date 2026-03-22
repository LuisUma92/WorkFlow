---
adr: "0000"
title: "SetFormat — Master package loader"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - packages
  - format
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0003"
  - "LATEX-STY/0004"
  - "LATEX-STY/0011"
---

## Context

Every LaTeX project needs a consistent set of packages for language, fonts,
math, graphics, bibliography, and color boxes. Loading them individually in
each document leads to version drift and conflicts.

---

## Decision

A single `.sty` file (`SetFormat.sty`) loads **all** shared packages in a
deterministic order. Two variants exist:

| File              | Engine   | Use case                |
|-------------------|----------|-------------------------|
| `SetFormat.sty`   | LuaLaTeX | Notes, thesis, lectures |
| `SetFormatP.sty`  | XeLaTeX  | Partial exams (legacy)  |

### Packages loaded (SetFormat.sty)

| Category       | Key packages                                              |
|----------------|-----------------------------------------------------------|
| Language       | `babel` (spanish)                                         |
| Fonts          | `luaotfload`, `fontspec`, `realscripts`, `unicode-math` (STIX Two) |
| Math           | `amsmath`, `bm`, `cancel`                                 |
| Units          | `siunitx`                                                 |
| Color          | `xcolor` (table option)                                   |
| Color boxes    | `tcolorbox` (breakable, skins, theorems, xparse, ...)     |
| Graphics       | `graphicx`, `tikz`, `pgfplots`, `subcaption`, `pdfpages`  |
| Tables         | `multirow`, `dcolumn`, `booktabs`                         |
| Bibliography   | `biblatex` (biber backend), `csquotes`                    |
| Layout         | `multicol`                                                |
| Hyperlinks     | `hyperref`, `url`                                         |
| Enumeration    | `enumerate`, `enumitem`                                   |

### SetFormatP.sty differences

- Uses **XeLaTeX** engine (`polyglossia`, `xltxtra`, `xunicode`).
- Fonts: Times New Roman via `fontspec` (not STIX Two).
- Loads `physics` package (dropped from SetFormat.sty).
- Includes inline color definitions (`BlueST`, `coolblack`).
- Defines `\unit` redirection and `\then` for presentations.

---

## Architectural Rules

### MUST

- All LaTeX documents **MUST** load format via symlink to `0-packages.sty`.
- `SetFormat.sty` **MUST** be compiled with LuaLaTeX.
- `SetFormatP.sty` **MUST** be compiled with XeLaTeX.

### MUST NOT

- Individual documents **MUST NOT** load packages already provided by SetFormat.

### SHOULD

- New packages **SHOULD** be added to `SetFormat.sty`, not per-project.

---

## Consequences

### Benefits

- Single point of package management across all projects
- No version conflicts between documents

### Costs

- All documents share the same package set (no per-project trimming)
- Two variants to maintain (LuaLaTeX vs XeLaTeX)

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                                     |
| ---------- | ------------------------------------------ |
| 2025-09-29 | Initial version (XeLaTeX, SetFormatP.sty)  |
| 2026-03-08 | Refactor: LuaLaTeX variant (SetFormat.sty) |
