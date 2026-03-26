---
adr: "0006"
title: "Color system — Physics palette and institutional themes"
status: Accepted
date: 2025-09-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - colors
  - institution
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "STY-0005"
  - "STY-0008"
---

## Context

Colors serve two purposes: semantic color-coding of physics quantities in
lectures, and institutional branding for exam headers and title pages.

---

## Decision

Four color files, each loaded contextually:

### ColorsLight.sty — Physics quantity palette

Maps physical quantities to HTML colors for use in equations and diagrams.

| Color name  | Hex       | Quantity              |
|-------------|-----------|-----------------------|
| `Pos`       | `#8D6E63` | Position              |
| `PosX/Y/Z`  | varies   | Position components   |
| `Dis`       | `#9C27B0` | Distance              |
| `Des`       | `#E91E63` | Displacement          |
| `Vel`       | `#3F51B5` | Velocity              |
| `Rap`       | `#673AB7` | Speed                 |
| `Ace`       | `#43A047` | Acceleration          |
| `Mas`       | `#0000F0` | Mass                  |
| `Fza`       | `#FF0000` | Force                 |
| `BlueBG`    | `#015298` | Backgrounds           |

### colors-UCR.sty — Universidad de Costa Rica

Institutional palette: `Uceleste`, `Uazul`, `Uamarillo`, `Unaranja`,
`Ucafe`, `Uverde` with numbered variants (19 colors total).

### colors-UCIMED.sty — Universidad de las Ciencias Médicas

Extended palette with primary (`Uazul`), secondary, accent tones,
warm/cool variants, and opacity levels. Includes named `tcolorbox`
backgrounds (70+ color definitions).

### colors-Ufide.sty — Universidad Fidélitas

Minimal palette for institutional branding.

---

## Architectural Rules

### MUST

- `ColorsLight.sty` **MUST** be loaded in all lecture documents.
- Institutional color files **MUST** be loaded via `SetProfiles.sty` commands.

### MUST NOT

- Documents **MUST NOT** redefine color names already in these files.

### SHOULD

- New colors **SHOULD** follow the `U{name}` prefix for institutional colors.

---

## Consequences

### Benefits

- Consistent visual identity per institution
- Physics colors decoupled from institutional branding

### Costs

- Four files to maintain
- UCIMED palette is significantly larger than others

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                            |
| ---------- | --------------------------------- |
| 2025-09-29 | Initial (ColorsLight, colors-UCR) |
| 2026-03-20 | colors-UCIMED, colors-Ufide added |
