---
adr: 0001
title: "Zettelkasten-based LaTeX Knowledge System with TikZ Visualization"
status: Proposed
date: 2026-03-24
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - knowledge-management
  - latex
  - tikz
decision_scope: system
supersedes: null
superseded_by: null
related_adrs: []
---

## Context

The system consists of a large collection of small, reusable LaTeX files that are included using `\input`. The goal is to evolve this into a Zettelkasten-like knowledge system, where each file represents a semantically independent note that can reference others.

Key requirements include:

- reusable modular content
- bidirectional or network-style linking between notes
- ability to reference notes semantically (not only structurally)
- visualization of relationships between notes
- integration with LaTeX compilation workflows

Initial ideas considered:

- using `\section`, `\label`, and `\ref` as the foundation of the system
- leveraging TikZ mindmaps for navigation
- embedding links manually using `\hyperlink`

However, these approaches present limitations:

- `\section` enforces hierarchical structure, not graph-based relationships
- `\label`/`\ref` are designed for document structure, not semantic nodes
- TikZ mindmaps are visual tools, not semantic storage systems
- manual hyperlinking is error-prone and non-scalable

A decision is required to define a scalable, maintainable architecture for managing interconnected LaTeX knowledge units.

---

## Decision Drivers

- maintainability of a large set of notes
- semantic clarity and separation of concerns
- scalability of inter-note linking
- consistency of references and identifiers
- reuse across multiple documents
- automation of navigation and indexing
- compatibility with LaTeX workflows
- extensibility toward graph visualization

---

## Decision

Adopt a **macro-based semantic layer on top of LaTeX** to implement a Zettelkasten-style knowledge system.

Key elements:

1. **Notes as first-class entities**
   - Each note is defined using a dedicated macro or environment (e.g., `\begin{zettelnote}`).
   - Each note has:
     - a stable unique identifier (ID)
     - a title
     - optional metadata (tags, aliases)

2. **Custom linking system**
   - All inter-note references MUST use a dedicated macro (e.g., `\zlink{id}`).
   - Underlying implementation uses `\hypertarget` and `\hyperlink`.

3. **Decoupling from document structure**
   - Notes MUST NOT rely on `\section` or other structural commands as primary identity.
   - Structural hierarchy is independent from semantic linking.

4. **Centralized metadata handling**
   - Titles and identifiers are registered once and reused automatically.
   - Avoid duplication of titles in references.

5. **TikZ as a visualization layer only**
   - TikZ (mindmap, trees, or graphdrawing) is used to visualize relationships.
   - TikZ MUST NOT be the source of truth for relationships.

6. **Hybrid graphics approach**
   - TikZ is the default for schematic, parametric, and physics diagrams.
   - External images (PNG/SVG/PDF) are embedded via TikZ nodes when needed.

---

## Architectural Rules

### MUST

- Each note **MUST define a stable unique identifier**.
- Notes **MUST be declared through a dedicated macro/environment**.
- Inter-note references **MUST use a custom linking macro**.
- Linking **MUST be implemented using `\hypertarget` and `\hyperlink`**.
- The semantic network **MUST be independent of LaTeX sectioning**.
- TikZ diagrams **MUST NOT encode semantic relationships as the primary data source**.

### SHOULD

- Notes **SHOULD include metadata** (tags, aliases).
- A centralized registry of notes **SHOULD be maintained**.
- Visualization graphs **SHOULD be generated from declarative relationships**.
- TikZ styles **SHOULD be standardized across diagrams**.

### MAY

- Backlinks **MAY be implemented in future iterations**.
- Graph visualization **MAY use advanced TikZ libraries (graphdrawing)**.
- External tools **MAY be used to precompute graph structures**.

---

## Implementation Notes

- Notes should live as individual `.tex` files and be included via `\input`.
- Recommended structure:

```

notes/
topic/
note-id.tex

```

- A note definition macro may look like:

```

\begin{zettelnote}{id}{Title}
...
\end{zettelnote}

```

- Linking macro:

```

\zlink{id}

```

- Internally:

```

\hypertarget{id}{Title}
\hyperlink{id}{Title}

```

- For diagrams:
  - TikZ should handle layout, vectors, axes, annotations.
  - External images should be embedded via `\node {\includegraphics{...}}`.

---

## Impact on AI Coding Agents

Agents modifying the system must follow these rules:

- Do not use `\section` as a substitute for note identity.
- Do not create raw `\hyperlink` or `\label` references between notes.
- Always use the defined abstraction layer (`zettelnote`, `\zlink`).
- Do not encode semantic relationships directly in TikZ diagrams.
- Maintain consistency of IDs across files.
- When adding notes, ensure uniqueness of identifiers.

Agents should extend macros rather than bypass them.

---

## Consequences

### Benefits

- clear separation between structure and semantics
- scalable knowledge graph within LaTeX
- improved maintainability and reuse
- consistent linking and navigation
- compatibility with visualization tools (TikZ)

### Costs

- increased upfront complexity
- need to design and maintain custom macros
- additional discipline required in note creation
- indirect workflow compared to standard LaTeX usage

---

## Alternatives Considered

### Alternative A: Section-based system

Use `\section`, `\label`, and `\ref` for all notes.

#### Advantages

- native LaTeX functionality
- simple to implement

#### Disadvantages

- enforces hierarchical structure
- poor support for graph-like relationships
- limited semantic expressiveness

---

### Alternative B: Manual hyperlinking

Use `\hyperlink` directly everywhere.

#### Advantages

- flexible
- minimal abstraction

#### Disadvantages

- error-prone
- not scalable
- no central control
- duplication of titles

---

### Alternative C: TikZ mindmap as primary system

Use TikZ mindmaps to represent and navigate all notes.

#### Advantages

- visual representation
- intuitive layout

#### Disadvantages

- not a semantic source of truth
- difficult to maintain at scale
- limited automation of relationships

---

## Compatibility / Migration

```

No immediate migration required.
Applies incrementally to new notes.

Existing content can be refactored progressively.

```

---

## References

- Niklas Luhmann — Zettelkasten Method
- Martin Fowler — Architectural Decision Records
- PGF/TikZ Manual
- LaTeX hyperref package documentation

---

## Status

**Proposed**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-24 | Initial ADR |
