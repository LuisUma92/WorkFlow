---
adr: 0002
title: "Unified Knowledge, Diagram, and Exercise System with Markdown, TikZ, and LaTeX DSL"
status: Proposed
date: 2026-03-24
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - knowledge-management
  - markdown
  - latex
  - tikz
  - exercises
  - moodle
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - 0001
---

## Context

ADR-0001 defines a Zettelkasten-based knowledge system implemented directly in LaTeX using semantic macros and TikZ for visualization.

However, further requirements emerged:

- need for a **single source of truth** across both teaching and research workflows
- separation between **knowledge representation** and **editorial output**
- integration of **Markdown-based note-taking workflows**
- scalable handling of **technical diagrams (TikZ)**
- structured management of **exercises and assessments**
- requirement to export exercises to **Moodle XML**
- need for **rich metadata** across notes and exercises

Additionally:

- LaTeX is optimal for rendering but not for semantic storage
- Markdown is optimal for semantic knowledge representation and linking
- exercises require structured semantics beyond visual LaTeX formatting
- diagrams must be reusable across multiple outputs

A new architectural decision is required to unify:

- Markdown knowledge notes
- TikZ diagram assets
- LaTeX-based exercises
- automated export pipelines

---

## Decision Drivers

- single source of truth for knowledge
- reuse across teaching and research
- separation of semantics and rendering
- interoperability (LaTeX, Markdown, Moodle)
- automation capability (CLI-based workflows)
- maintainability and scalability
- consistency across formats
- extensibility for future tooling

---

## Decision

Adopt a **layered architecture separating knowledge, assets, exercises, and outputs**, with distinct canonical formats for each.

### 1. Knowledge Layer (Canonical)

- Markdown (`.md`) is the **primary source of truth for knowledge**.
- Each note:
  - contains semantic content
  - uses YAML frontmatter
  - supports bidirectional linking
- LaTeX is **not used as the primary knowledge container**.

---

### 2. Diagram Layer (TikZ Asset Model)

- All complex diagrams MUST be defined as **standalone TikZ `.tex` files**.
- Diagrams are compiled into:
  - PDF (primary artifact)
  - SVG (optional for Markdown preview)
- Markdown notes reference **rendered artifacts**, not TikZ source.

---

### 3. Exercise Layer (LaTeX DSL)

- Exercises MUST be defined in `.tex` using a **restricted semantic macro DSL**.
- LaTeX is used as a **structured declarative format**, not only for rendering.

Each exercise consists of:

- YAML-like metadata (commented frontmatter)
- structured macros for:
  - stem
  - options
  - answers
  - feedback
  - solution

---

### 4. Metadata Strategy

- Markdown files use **native YAML frontmatter**
- `.tex` files use **commented YAML blocks at the top**

Example:

```tex
% ---
% id: phys-gauss-001
% type: multichoice
% difficulty: medium
% tags: [physics, electrostatics]
% concepts:
%   - 20260320-physics-gauss-law
% ---
```

- This metadata is consumed exclusively by external tooling (CLI).

---

### 5. CLI Orchestration Layer

A Python CLI MUST act as the central orchestrator:

Responsibilities:

- parse Markdown notes
- parse `.tex` exercises (DSL + metadata)
- validate schemas
- resolve concept references
- build outputs:
  - LaTeX documents
  - Moodle XML
  - practice sets
  - exams

---

### 6. Output Layer

Outputs are **derived artifacts only**, including:

- PDF (LaTeX)
- slides
- exams
- Moodle XML
- summaries

Outputs MUST NOT be treated as source of truth.

---

## Architectural Rules

### MUST

- Knowledge **MUST be stored in Markdown (`.md`) files**.
- Exercises **MUST be stored in `.tex` using a controlled macro DSL**.
- Complex diagrams **MUST be defined as standalone TikZ files**.
- Rendered diagrams (PDF/SVG) **MUST be referenced from Markdown**, not embedded as raw TikZ.
- `.tex` exercise files **MUST include metadata via commented YAML blocks**.
- CLI tooling **MUST be responsible for parsing and exporting all structured data**.
- Moodle XML **MUST be generated, not manually authored**.
- Outputs **MUST NOT be treated as canonical sources**.

---

### SHOULD

- Exercises **SHOULD reference knowledge notes via stable IDs**.
- Metadata schemas **SHOULD be validated automatically**.
- TikZ diagrams **SHOULD be reusable across multiple contexts**.
- Naming conventions **SHOULD align between notes, diagrams, and exercises**.
- CLI tools **SHOULD support linting and indexing**.

---

### MAY

- SVG exports **MAY be generated for improved Markdown visualization**.
- Additional metadata fields **MAY be introduced as needed**.
- Alternative export formats (HTML, JSON) **MAY be supported in future**.
- A future intermediate representation (e.g., JSON/YAML canonical exercises) **MAY be introduced**.

---

## Implementation Notes

### Directory structure

```
knowledge-base/
├── notes/
│   ├── permanent/
│   ├── literature/
│
├── exercises/
│   ├── physics/
│   ├── neurology/
│
├── assets/
│   ├── tikz/
│   ├── figures/
│
├── outputs/
│   ├── exams/
│   ├── moodle/
│
├── tools/
│   ├── cli/
```

---

### TikZ workflow

- source: `assets/tikz/*.tex`
- output: `assets/figures/*.pdf` (+ optional `.svg`)
- Markdown references rendered figures

---

### Exercise DSL expectations

Exercises MUST define:

- stem (`\qstem`)
- options (`\qoption`)
- correctness (flags or arguments)
- feedback (`\qgeneralfeedback`)
- solution (`\qsolution`)

---

### CLI modules (minimum)

- `validate`
- `parse`
- `export-moodle`
- `build-pdf`
- `index`

---

## Impact on AI Coding Agents

Agents must:

- Treat Markdown as the canonical knowledge layer
- Treat `.tex` exercises as structured DSL, not free-form LaTeX
- Never generate Moodle XML directly without going through the CLI pipeline
- Respect metadata schemas in both Markdown and `.tex`
- Avoid embedding TikZ directly in Markdown for complex diagrams
- Maintain ID consistency across notes, exercises, and diagrams

Agents should reuse existing abstractions instead of introducing parallel structures.

---

## Consequences

### Benefits

- unified knowledge system across teaching and research
- strong separation between semantics and rendering
- high reusability of diagrams and exercises
- scalable export to multiple formats
- compatibility with Markdown-based workflows
- maintainable long-term architecture

---

### Costs

- increased architectural complexity
- need for CLI tooling development
- discipline required in metadata and DSL usage
- dual-format system (Markdown + LaTeX)

---

## Alternatives Considered

### Alternative A: LaTeX-only system

#### Advantages

- single format
- strong rendering capabilities

#### Disadvantages

- poor semantic structure
- difficult automation
- weak interoperability

---

### Alternative B: Markdown-only system (no LaTeX DSL)

#### Advantages

- simple
- highly portable

#### Disadvantages

- insufficient for complex math and exercises
- weak control over rendering
- limited reuse in academic outputs

---

### Alternative C: Direct Moodle XML authoring

#### Advantages

- no conversion step

#### Disadvantages

- not human-friendly
- poor maintainability
- tightly coupled to LMS

---

## Compatibility / Migration

```
No breaking changes to ADR-0001.

This ADR extends the system:

- introduces Markdown as canonical knowledge layer
- redefines role of TikZ as external asset
- formalizes exercise system and CLI pipeline

Existing LaTeX notes can be progressively migrated to Markdown.
Existing exercises can be adapted to the DSL incrementally.
```

---

## References

- ADR-0001 Zettelkasten system
- Pandoc documentation
- Moodle XML format documentation
- PGF/TikZ Manual
- Zettelkasten methodology

---

## Status

**Proposed**

---

## Change Log

| Date       | Change                         |
| ---------- | ------------------------------ |
| 2026-03-24 | Initial ADR extending ADR-0001 |
