---
adr: "0007"
title: "VectorPGF — TikZ styles for vector diagrams"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - tikz
  - diagrams
  - vectors
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0001"
---

## Context

Physics lectures require consistent vector diagrams with uniform arrow styles,
axis rendering, grid overlays, and angle arcs. Defining these per-document
leads to visual inconsistency.

---

## Decision

`VectorPGF.sty` defines reusable TikZ styles for HD-quality vector diagrams.

### Styles

| Style          | Description                                |
|----------------|--------------------------------------------|
| `Vector`       | Thick line (1.1pt), Stealth arrowhead 16pt |
| `VectorAngle`  | Thin line (0.8pt), Latex arrowhead 4pt     |
| `Axis`         | Standard arrow, black, 0.9pt               |
| `Grids`        | 0.5cm step, very thin, gray!30             |
| `Proyections`  | Dashed, 1.1pt                              |

### Global node defaults

All nodes: `fill=white`, `fontsize{16}{19}` for readability on backgrounds.

### Helper commands

- `\printvalue[precision]{value}` — formatted number output.
- `\axisextra` — axis extension factor (0.2).
- Angle arc radii: `\rtheta` (0.8), `\ralpha` (0.6), `\rbeta` (0.4).
- Template vectors A and B with magnitude/angle macros.

---

## Architectural Rules

### MUST

- Vector diagrams in lectures **MUST** use these styles for consistency.

### SHOULD

- New TikZ styles for diagrams **SHOULD** be added to this file.

---

## Consequences

### Benefits

- Uniform visual quality across all lecture vector diagrams
- Pre-calculated vector macros speed up diagram creation

### Costs

- Fixed arrowhead sizes tuned for HD presentation, may need adjustment for print

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
