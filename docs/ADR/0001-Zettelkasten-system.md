---
adr: 0001
title: "Zettelkasten Note Semantic Layer in LaTeX"
status: Accepted
date: 2026-03-24
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - knowledge-management
  - latex
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "0002"
---

## Context

The system consists of a large collection of small, reusable LaTeX files included via `\input`. The goal is to evolve this into a Zettelkasten-like knowledge system where each file is a semantically independent note that can reference others.

Approaches considered and rejected:

- `\section`/`\label`/`\ref` — enforces hierarchy, not graph relationships
- Raw `\hyperlink` everywhere — error-prone, not scalable, duplicates titles
- TikZ mindmaps as primary system — visual tool, not semantic storage

A macro-based semantic layer is needed to manage interconnected LaTeX knowledge units.

---

## Decision

Adopt a **macro-based semantic layer on top of LaTeX** for note identity and linking.

1. **Notes as first-class entities** — each note uses a dedicated macro/environment (e.g., `\begin{zettelnote}{id}{Title}`) with a stable unique ID, title, and optional metadata.

2. **Custom linking** — all inter-note references use `\zlink{id}`, implemented via `\hypertarget`/`\hyperlink`.

3. **Decoupled from document structure** — note identity is independent of `\section` or other structural commands.

4. **Centralized metadata** — titles and IDs are registered once and reused automatically.

---

## Architectural Rules

### MUST

- Each note **MUST define a stable unique identifier**.
- Notes **MUST be declared through a dedicated macro/environment**.
- Inter-note references **MUST use `\zlink`**, not raw `\hyperlink` or `\label`/`\ref`.
- The semantic network **MUST be independent of LaTeX sectioning**.

### SHOULD

- Notes **SHOULD include metadata** (tags, aliases).
- A centralized registry of notes **SHOULD be maintained** (via CLI/DB).

### MAY

- Backlinks **MAY be implemented in future iterations**.
- External tools **MAY precompute graph structures** for visualization.

---

## Implementation Notes

- Notes live as individual `.tex` files under `notes/topic/`.
- Note macro: `\begin{zettelnote}{id}{Title} ... \end{zettelnote}`
- Link macro: `\zlink{id}` → `\hyperlink{id}{Title}`
- Existing `\excref`/`\exhyperref` macros in `SetCommands.sty` serve a similar role for cross-document references and should be aligned with `\zlink`.

---

## Impact on AI Coding Agents

- Do not use `\section` as a substitute for note identity.
- Do not create raw `\hyperlink` or `\label` references between notes.
- Always use `\zlink` or the defined abstraction layer.
- Maintain uniqueness of IDs across files.
- Extend macros rather than bypass them.

---

## Consequences

### Benefits

- Clear separation between structure and semantics
- Scalable knowledge graph within LaTeX
- Consistent linking and navigation

### Costs

- Custom macros require design and maintenance
- Additional discipline in note creation

---

## Compatibility / Migration

No immediate migration required. Applies incrementally to new notes. Existing content refactored progressively.

---

## References

- Niklas Luhmann — Zettelkasten Method
- LaTeX hyperref package documentation

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                                          |
| ---------- | ----------------------------------------------- |
| 2026-03-24 | Initial ADR                                     |
| 2026-03-25 | Narrowed scope to note layer only; TikZ and exercises moved to separate ADRs. Accepted. |
