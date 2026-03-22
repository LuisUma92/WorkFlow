---
adr: "0002"
title: "SetCommands — Shared macros and directories"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - macros
  - commands
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0005"
---

## Context

Math notation, directory paths, boolean flags, and example counters are
repeated across every document. Centralizing them avoids drift and enables
global changes.

---

## Decision

`SetCommands.sty` provides:

### Directory macros

```latex
\newcommand{\mytex}{/home/luis/.config/mytex}
\newcommand{\FisicaDir}{/home/luis/Documents/01-U/00-Fisica}
\newcommand{\IMGfolder}{\FisicaDir/00II-ImagesFigures}
```

### Boolean flags

- `test` — show/hide test-mode content.
- `solutions` — show/hide solutions.
- `main` — flag for main document vs subfile.

### Example counter

`\exa[chapter]{number}` — auto-incremented example numbering, section-reset,
with optional chapter prefix.

### Math shorthand

| Command      | Output                  |
|--------------|-------------------------|
| `\vc{x}`     | Bold vector with arrow  |
| `\vh{x}`     | Bold unit vector (hat)  |
| `\vm{x}`     | Bold math symbol        |
| `\scrp{x}`   | Scriptsize text         |
| `\ala{n}`    | Superscript (text mode) |

---

## Architectural Rules

### MUST

- Directory paths **MUST** use these macros, never hardcoded paths in documents.
- Boolean flags **MUST** be toggled via `\setboolean`, not redefined.

### SHOULD

- New shared macros **SHOULD** be added here, not in individual documents.

---

## Consequences

### Benefits

- Single source of truth for paths and notation
- Example numbering consistent across all documents

### Costs

- Directory macros contain hardcoded absolute paths

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2025-09-29 | Initial ADR |
