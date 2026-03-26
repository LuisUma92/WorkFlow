---
adr: "0004"
title: "SetUnits — SI unit extensions"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - siunitx
  - physics
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "STY-0000"
---

## Context

The `siunitx` package provides standard SI units, but physics courses require
additional units (barn, angular velocity) and domain-specific shorthands
(density types, temperature symbols).

---

## Decision

`SetUnits.sty` configures `siunitx` globally and declares custom units.

### Global configuration

```latex
\sisetup{
  detect-all,
  mode = math,
  per-mode = power,
  inter-unit-product = \,,
}
```

### Custom units

| Command             | Definition | Domain               |
|---------------------|------------|----------------------|
| `\barn`             | b          | Nuclear physics      |
| `\fbarn`            | fb         | Particle physics     |
| `\luminosity`       | cm⁻²s⁻¹   | Particle physics     |
| `\degC`, `\degF`    | °C, °F     | Temperature          |
| `\ace`              | m/s²       | Mechanics            |
| `\vel`              | m/s        | Mechanics            |
| `\denV/A/L`         | kg/m³²¹   | Density (vol/area/lin) |
| `\angvel`, `\angace`| rad/s(²)   | Rotational mechanics |

---

## Architectural Rules

### MUST

- All custom units **MUST** be declared via `\DeclareSIUnit`.
- `siunitx` configuration **MUST** remain in this file, not in documents.

### SHOULD

- New physics units **SHOULD** be added here as `\DeclareSIUnit`.

---

## Consequences

### Benefits

- Uniform unit formatting across all documents
- Custom shorthands reduce typing and errors

### Costs

- Depends on `siunitx` being loaded by SetFormat

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2025-09-29 | Initial ADR |
