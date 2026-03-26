---
adr: 0009
title: "Exercise Module Boundary and Shared LaTeX Parsing"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - exercises
  - latex
  - module-boundary
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "Zettelkasten/0005"
  - "Zettelkasten/0006"
  - "Zettelkasten/0007"
---

## Context

Phase 4 introduces an exercise parser, domain model, Moodle exporter, and CLI commands. Two questions arise:

1. **Where does the exercise module live?**
2. **Should LaTeX parsing primitives be shared across modules?**

ADR-0005 originally suggested `src/latexzettel/api/exercises.py`, but exercises are a distinct domain from Zettelkasten notes. `src/workflow/` has emerged as the shared infrastructure namespace (ADR-0007), hosting `db/`, `tikz/`, and `validation/`.

Both `workflow.tikz` and `workflow.exercise` need brace-aware LaTeX parsing — tikz for extracting commented YAML from standalone `.tex` files, exercises for extracting `\question`, `\qpart`, and other macros. Duplicating this logic creates a maintenance burden.

### Exercise Origins

Exercises have two distinct origins:

- **Book exercises**: Generated from textbook references (chapter, section, exercise number). These start as placeholders created by `crete` and evolve as solutions are written.
- **Evaluation exercises**: Created for specific exams/quizzes. May be original or adapted from book exercises.

Both types must work across institutions (UCR, UFide, UCIMED), each with different:
- Academic cycles (18-week semester, 15-week quarter, 24-week semester)
- Exam formatting rules and instructions
- Enumeration styles (UFide uses "Desempeño" performance-based labeling)
- Point tracking conventions

### Options Considered

**Option A: `src/latexzettel/api/exercises.py`** (original ADR-0005 suggestion)
- Con: latexzettel's scope is Zettelkasten notes, not academic exercises
- Con: Creates dependency from latexzettel → ITEP's taxonomy/institution models

**Option B: `src/workflow/exercise/`** (selected)
- Pro: Exercises are a cross-cutting concern like tikz/ and validation/
- Pro: Natural access to workflow.db models (Exercise, Content, EvaluationTemplate)
- Pro: Keeps latexzettel focused on its Zettelkasten role
- Pro: Mirrors established pattern: `workflow.tikz`, `workflow.validation`, `workflow.exercise`

**Option C: `src/lectkit/exercise/`**
- Con: lectkit is a utility grab-bag without a coherent domain

---

## Decision

### Part 1: Exercise module at `src/workflow/exercise/`

```
src/workflow/exercise/
├── __init__.py
├── domain.py      # ParsedExercise, ParsedOption, ParseResult (frozen dataclasses)
├── parser.py      # .tex file → ParsedExercise (uses workflow.latex for brace extraction)
├── moodle.py      # ParsedExercise → Moodle XML (with LaTeX normalization)
├── assembler.py   # EvaluationTemplate + exercise bank → exam document
└── cli.py         # Click command group: parse, list, export-moodle, build-exam, sync
```

### Part 2: Shared LaTeX parsing at `src/workflow/latex/`

Common LaTeX parsing primitives are extracted into a shared module, consumed by both `workflow.tikz` and `workflow.exercise`:

```
src/workflow/latex/
├── __init__.py
├── braces.py      # extract_brace_arg(), extract_macro_args() — brace-counting logic
├── comments.py    # extract_commented_yaml(), strip_comments() — YAML-in-comments
└── normalize.py   # expand_custom_macros() — resolve shared/sty macros to basic LaTeX
```

This avoids duplicating brace-counting logic and gives future modules (Phase 5 lectures, Phase 6 graph) the same parsing toolkit.

### Dependency Direction

```
workflow.latex                → (no workflow dependencies — pure parsing utilities)
workflow.exercise.parser      → workflow.latex (brace extraction, YAML extraction)
workflow.exercise.parser      → workflow.validation.schemas (ExerciseMetadata)
workflow.exercise.domain      → itep.structure (TaxonomyLevel, TaxonomyDomain)
workflow.exercise.moodle      → workflow.latex.normalize (custom macro expansion)
workflow.exercise.cli         → workflow.db.repos (ExerciseRepo)
workflow.tikz                 → workflow.latex (YAML-in-comments extraction)
```

latexzettel has **no dependency** on workflow.exercise or workflow.latex, and vice versa.

### Institutional Awareness

The exercise module does not hardcode institutional rules. Instead:
- `EvaluationTemplate` (per institution) defines exam structure constraints
- `Institution.cycle_weeks` and `Institution.cycle_name` inform scheduling
- Exam formatting (instructions, headers, enumeration) is driven by LaTeX templates in `shared/templates/{UCR,UCIMED}-PPI.tex` and `title-ufide.tex`
- `workflow.exercise.assembler` reads the institution from the `EvaluationTemplate` FK and selects the appropriate formatting

---

## Architectural Rules

### MUST

- Exercise module **MUST** live in `src/workflow/exercise/`.
- Shared LaTeX parsing **MUST** live in `src/workflow/latex/`.
- Domain types (`ParsedExercise`, `ParsedOption`) **MUST** be immutable (frozen dataclasses).
- Parser **MUST** reuse `ExerciseMetadata` from `workflow.validation.schemas` for YAML metadata.
- `workflow.latex` **MUST** have zero dependencies on other workflow modules (pure utilities).

### SHOULD

- CLI commands **SHOULD** follow the same Click group pattern as `tikz` and `validate`.
- `crete` (lectkit) **SHOULD** be refactored to delegate to `workflow.exercise` for generation logic.
- `workflow.tikz` **SHOULD** migrate its YAML-in-comments parsing to use `workflow.latex.comments`.

### MUST NOT

- latexzettel **MUST NOT** import from `workflow.exercise` or `workflow.latex`.
- `workflow.exercise` **MUST NOT** import from latexzettel.
- `workflow.latex` **MUST NOT** import from `workflow.exercise`, `workflow.tikz`, or latexzettel.

---

## Consequences

### Benefits

- Clean module boundaries: each namespace has a single, coherent domain
- Shared LaTeX parsing avoids duplication between tikz and exercise parsers
- `workflow.latex.normalize` provides a single place for custom-macro expansion (critical for Moodle export)
- Institutional differences handled via DB-driven templates, not code branches

### Costs

- ADR-0005 implementation notes must be updated (parser location changed)
- Three new packages instead of one (exercise, latex, and updated tikz)
- `workflow.latex` is a new dependency that tikz must adopt

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
| 2026-03-25 | Rev 2: Add workflow.latex shared module, institutional awareness, exercise origins |
