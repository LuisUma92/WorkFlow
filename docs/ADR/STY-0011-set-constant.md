---
adr: "0011"
title: "SetConstant — Physical constants reference table"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - physics
  - constants
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0004"
---

## Context

Physics documents frequently reference fundamental constants (speed of light,
Planck's constant, elementary charge, etc.). Hardcoding values in each
document risks inconsistency and transcription errors.

---

## Decision

`SetConstant.sty` defines LaTeX commands for CODATA-recommended values of
fundamental physical constants. Each constant has a symbol command and a
value command.

### Constants defined

| Constant          | Symbol cmd | Value cmd   | SI value                    |
|-------------------|------------|-------------|-----------------------------|
| Speed of light    | `\vcs`     | `\cval`     | 299 792 458 m/s             |
| Planck's constant | `\hps`     | `\hpval`    | 6.626 070 15 × 10⁻³⁴ J·s   |
| Planck's (eV)     | —          | `\hpvalev`  | 4.135 667 696 × 10⁻¹⁵ eV·s |
| Reduced Planck    | `\hbs`     | `\hbval`    | 1.054 571 817 × 10⁻³⁴ J·s  |
| Reduced (eV)      | —          | `\hbvalev`  | 6.582 119 569 × 10⁻¹⁶ eV·s |
| Elementary charge | `\ecs`     | `\ecval`    | 1.602 176 634 × 10⁻¹⁹ C    |
| Boltzmann         | `\kbs`     | `\kbval`    | 1.380 649 × 10⁻²³ J/K      |
| Avogadro          | `\nas`     | `\naval`    | 6.022 140 76 × 10²³ mol⁻¹  |

Additional constants are listed in comments (Wien, permeability,
permittivity, gravitational, electron/proton/neutron mass, Rydberg,
Bohr radius, gas constant, Stefan-Boltzmann).

### Naming convention

- `\{abbr}s` — symbol in math mode (e.g. `\vcs` → $c$).
- `\{abbr}val` — numeric value (e.g. `\cval` → 299792458).
- `\{abbr}valev` — value in eV units where applicable.

---

## Architectural Rules

### MUST

- Values **MUST** use CODATA recommended values.
- Symbol commands **MUST** wrap in `$...$` for inline math.

### SHOULD

- Commented constants **SHOULD** be promoted to commands when needed.

---

## Consequences

### Benefits

- Single source of truth for physical constants
- Consistent precision across all documents

### Costs

- Values must be manually updated when CODATA revises recommendations

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2025-09-29 | Initial ADR |
