---
adr: "0005"
title: "SetSymbols — Color-coded physics notation"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - symbols
  - physics
  - color
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "STY-0006"
  - "STY-0002"
---

## Context

Physics lectures benefit from consistent color-coding of quantities
(position in brown, velocity in blue, force in red, etc.). Students
can visually track each quantity across derivations and diagrams.

---

## Decision

`SetSymbols.sty` defines a color-coded symbol system for mechanics.
Each physical quantity has a vector and scalar variant.

### Symbol categories

| Quantity         | Color      | Vector      | Scalar    |
|------------------|------------|-------------|-----------|
| Position         | `Pos`      | `\vpos`     | `\spos`   |
| Components x,y,z | `PosX/Y/Z`| —           | `\sposx/y/z` |
| Unit vectors     | `PosX/Y/Z` | —          | `\uvi/j/k`|
| Distance         | `Dis`      | —           | `\sdis`   |
| Displacement     | `Des`      | `\vdes`     | `\sdes`   |
| Velocity         | `Vel`      | `\vvel`     | `\svel`   |
| Speed            | `Rap`      | —           | `\srap`   |
| Acceleration     | `Ace`      | `\vace`     | `\sace`   |
| Mass             | `Mas`      | —           | `\smas`   |
| Force            | `Fza`      | `\vfza`     | `\sfza`   |
| Linear momentum  | `MomL`     | `\vmom`     | `\smom`   |
| Angular momentum | `MomA`     | `\vmoma`    | `\smoma`  |
| Energy (E/K/U)   | `Ene/K/U`  | —           | `\sene/k/u` |

### Helper macro

```latex
\newcommand{\cvec}[2]{\vec{\symbf{\textcolor{#1}{#2}}}}
```

### Generic vectors A/B

Named vectors `\vA`, `\vB` (red/blue) with component accessors
(`\vAx`, `\vBy`, etc.) and angle (`\vAt`, `\vBt`).

### Script R (Griffiths notation)

`\rcurs`, `\brcurs`, `\hrcurs` — separation vector script-R via embedded PNG.

---

## Architectural Rules

### MUST

- Color names **MUST** match those defined in `ColorsLight.sty`.
- Vector commands **MUST** use `\cvec` helper for consistency.

### SHOULD

- New quantities **SHOULD** follow the `\v{qty}` / `\s{qty}` naming pattern.

---

## Consequences

### Benefits

- Visual consistency across lectures and exams
- Students identify quantities by color

### Costs

- Depends on `ColorsLight.sty` color definitions
- Script-R uses embedded PNG images (not scalable)

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                         |
| ---------- | ------------------------------ |
| 2025-09-29 | Initial ADR                    |
| 2026-03-08 | Refactored with `\cvec` helper |
