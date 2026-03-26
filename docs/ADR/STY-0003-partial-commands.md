---
adr: "0003"
title: "PartialCommands — Exam scoring and structure"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - exams
  - evaluation
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0000"
  - "LATEX-STY/0009"
---

## Context

Partial exams require structured point tracking, section consolidation,
answer-key toggling, and metadata (exam name, group, cycle). These commands
are only used in evaluation documents, not in notes or thesis.

---

## Decision

`PartialCommands.sty` provides:

### Counters

- `partialNumber` — exam number (I, II, III...).
- `totalPoints`, `sectionPoints`, `points` — accumulated scoring.
- Registered with `\regtotcounter` for cross-reference.

### Scoring commands

| Command                      | Purpose                                  |
|------------------------------|------------------------------------------|
| `\pts[add]{n}`               | Print "(n pts.)", optionally accumulate  |
| `\upt[add]`                  | Print "(1 pt.)", optionally accumulate   |
| `\uptcu`, `\ptscu{n}`        | "c/u" (each) variants                   |
| `\consolidatePoints{label}`  | Save section total, write to aux file    |
| `\ptsdistro`                 | Print point-distribution paragraph       |

### Metadata

- `\testdefinition{group}{cycle}{partialNumber}` — sets all exam metadata.
- `\settopics{text}` — topics covered in the exam.

### Answer toggling

- `\rightoption` — prints colored checkmark when `solutions` boolean is true.

---

## Architectural Rules

### MUST

- Exam documents **MUST** call `\testdefinition` before content.
- Points **MUST** be consolidated per section via `\consolidatePoints`.

### MUST NOT

- `PartialCommands.sty` **MUST NOT** be loaded in non-exam documents.

---

## Consequences

### Benefits

- Automatic point totals and cross-referenced section scores
- Answer key generated from same source as exam

### Costs

- Tightly coupled to the `solutions` boolean from SetCommands

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2025-09-29 | Initial ADR |
