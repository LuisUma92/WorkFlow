---
id: 0015
title: "Zettelkasten System Refactor"
aliases:
  - ADR-0015
status: Accepted
date: 2026-04-05
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - knowledge-management
  - latex
  - markdown
decision_scope: system
supersedes: 0001
superseded_by: null
related_adrs:
  - "0001"
  - "0002"
---

## Context

The system consists of a large collection of small, reusable markdown files on a central vault. This files are rendered into LaTeX atomic files included via `\input` for usage in documents (papers, resumes, lectures notes). The goal is to evolve this into a Zettelkasten-like knowledge system where each file is a semantically independent note that can reference others.

Approaches considered and rejected:

- `\section`/`\label`/`\ref` — enforces hierarchy, not graph relationships
- Raw `\hyperlink` everywhere — error-prone, not scalable, duplicates titles
- TikZ mindmaps as primary system — visual tool, not semantic storage
- LaTeX file as source of truth - complicate macro layer to manage interconnectivity.

---

## Decision

1. **Notes as first-class entities** — each note uses a dedicated yaml header to with a stable unique ID, title, and optional metadata. The note content is writing in the markdown file.

2. **Custom linking** — all inter-note references use `[[id|text]]`, if needed translated to `\zlink{id}` for LaTeX referencing system, implemented via `\hypertarget`/`\hyperlink`.

3. **Decoupled from document structure** — note identity is independent of `\section` or other structural commands.

4. **Centralized metadata** — titles and IDs are registered once and reused automatically.

5. **LaTeX only content** - images defined as tikz, exercises and mathematical demonstrations. This are references by the file if as needed.

6. **TikZ images** - all on central image vault `0000II-ImagesFigures` as tex files. Exists a rendering pipeline for usage, markdown only references the svg output, LaTeX projects includes PDF.

7. **Exercises stem and solution** - lives as LaTeX file on its own vault `0000EE-ExamplesExercises`. Exists a translation pipeline into Moodle xml that can be initialize by the user. ,

8. **Mathematical demonstrations** - Are the examples, needs macro specific to this use case.

---

## Architectural Rules

### MUST

- Each note **MUST define a stable unique identifier**.
- Inter-note references on LaTeX **MUST use `\zlink`**, not raw `\hyperlink` or `\label`/`\ref`.
- The semantic network **MUST be independent of LaTeX sectioning**.
- Notes **MUST be written as final text**.
- LaTeX translation **MUST only include renderable text for final compilation**.

### SHOULD

- Notes **SHOULD include metadata** (tags, aliases).
- A centralized registry of notes **SHOULD be maintained** (via CLI/DB).
- Metadata **SHOULD include references to Examples, Exercises and Images if applicable**.
- Project main document **SHOULD include all images referenced in the metadata of a note**.

### MAY

- Backlinks **MAY be implemented in future iterations**.
- External tools **MAY precompute graph structures** for visualization.
- ITeP **MAY implement commands to extract references to images, examples and exercises**.
- Temporal notes **MAY be written into a monolithic LaTeX file with (`%>note/name.ext`, `%>END`) dividers for extracting information into consolidate notes, TikZ images, examples of exercises**.
- Neovim plug-in **MAY be implemented to facilitate reproducibility**.

---

## Implementation Notes

- Notes live as individual `.md` files under `notes/`.
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

| Date       | Change      |
| ---------- | ----------- |
| 2026-04-05 | Initial ADR |
