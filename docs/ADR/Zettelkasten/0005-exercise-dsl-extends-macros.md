---
adr: 0005
title: "Exercise DSL Extends Existing LaTeX Macros"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - exercises
  - latex
  - moodle
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "Zettelkasten/0001"
  - "LATEX-STY/0002"
  - "LATEX-STY/0003"
---

## Context

A mature exercise macro system already exists in `shared/sty/` and is deployed across UCR, UFide, and UCIMED:

**SetCommands.sty** provides:
- `\question{stem}{solution}` — toggled by `test`/`solutions` booleans
- `\qpart{points}{solution}` — sub-question with solution toggle
- `\exa[ch]{num}` — exercise numbering

**PartialCommands.sty** provides:
- `\pts{n}`, `\upt`, `\ptscu`, `\uptcu` — point tracking
- `\consolidatePoints{label}` — section point totals
- `\rightoption` — answer key checkmark
- `\testdefinition{group}{cycle}{partial}` — exam metadata

The exercise template (`shared/templates/TNNE000.tex`) uses these macros.

New requirements include CLI-parseable metadata and Moodle XML export. These must be added **without breaking** the existing macro system.

---

## Decision

**Extend** the existing exercise macros with optional annotations. Do not replace them.

### New macros (additive)

- `\qfeedback{...}` — general feedback text (for Moodle export)
- `\qdiagram{tikz-asset-id}` — reference to a TikZ diagram asset

### Commented YAML metadata (additive)

Exercise `.tex` files gain an optional commented YAML block at the top:

```tex
% ---
% id: phys-gauss-001
% type: multichoice
% difficulty: medium
% taxonomy_level: Usar-Aplicar
% taxonomy_domain: Procedimiento Mental
% tags: [physics, electrostatics]
% concepts:
%   - 20260320-physics-gauss-law
% ---
```

- `taxonomy_level` and `taxonomy_domain` align with ITEP's `TaxonomyLevel` and `TaxonomyDomain` enums (from `itep/structure.py`).
- This metadata is consumed by CLI tooling only; LaTeX ignores it as comments.

### Preserved macros (no changes)

All existing macros (`\question`, `\qpart`, `\pts`, `\consolidatePoints`, `\rightoption`, `\testdefinition`, `\exa`) remain unchanged and compilable.

---

## Architectural Rules

### MUST

- Existing macros **MUST NOT be modified or renamed**.
- New macros **MUST be additive** — exercise files without them must still compile.
- Commented YAML metadata **MUST be optional** — exercises without it are valid LaTeX.
- `taxonomy_level` values **MUST match** ITEP's `TaxonomyLevel` enum.
- `taxonomy_domain` values **MUST match** ITEP's `TaxonomyDomain` enum.

### SHOULD

- CLI tooling **SHOULD warn** on exercises missing metadata (not error).
- New macros **SHOULD live in a dedicated `.sty` file** (e.g., `SetExercises.sty`).
- Moodle XML export **SHOULD use `xml.etree.ElementTree`**, not string templating.

### MAY

- A future intermediate representation (JSON/YAML) **MAY be introduced** for exercises.

---

## Implementation Notes

- Parser lives in `src/latexzettel/api/exercises.py`.
- Regex for commented YAML: lines matching `^% ---` to `^% ---` with `^% key: value` between.
- `\question{stem}{solution}` maps to Moodle `<questiontext>` + `<generalfeedback>`.
- `\qpart` with `\rightoption` maps to Moodle `<answer fraction="100">`.
- `\pts{n}` maps to Moodle `<defaultgrade>`.
- `crete` (lectkit) will be subsumed into the `exercise` CLI command group. Its JSON-based book metadata is replaced by ITEP's `Book`/`Content` DB tables.

---

## Impact on AI Coding Agents

- Never rename or modify existing macros in `SetCommands.sty` or `PartialCommands.sty`.
- New exercise-related macros go in `SetExercises.sty` only.
- When generating exercise files, always include commented YAML metadata.
- Respect taxonomy enum values from `itep/structure.py`.

---

## Consequences

### Benefits

- Zero disruption to existing LaTeX workflow across institutions
- Exercises become CLI-parseable and exportable to Moodle
- Taxonomy alignment with ITEP's evaluation system

### Costs

- Commented YAML is a convention, not enforced by LaTeX
- Parser must handle exercises with and without metadata

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
