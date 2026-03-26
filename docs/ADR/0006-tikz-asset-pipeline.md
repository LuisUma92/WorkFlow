---
adr: 0006
title: "TikZ Standalone Asset Pipeline"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - tikz
  - diagrams
  - assets
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "0001"
  - "0002"
  - "STY-0007"
---

## Context

TikZ diagrams are used extensively for physics diagrams, vector fields, and schematics. Currently they are embedded inline in LaTeX documents, making them non-reusable across multiple outputs (notes, exercises, slides, Markdown).

ADR-0002 establishes that Markdown notes reference rendered artifacts (PDF/SVG), not TikZ source. ITEP's `LectureProject` template already includes `lect/svg/` and `lect/img/` directories.

A standalone compilation pipeline is needed so that TikZ sources are compiled once and referenced by any consumer.

---

## Decision

TikZ diagrams are **standalone assets** compiled independently into PDF and SVG.

1. **Source convention**: each diagram is a `\documentclass[tikz]{standalone}` file under `assets/tikz/`.
2. **Compilation**: CLI command `tikz build` compiles all sources to PDF via `latexmk`, optionally converts to SVG via `dvisvgm` or `pdf2svg`.
3. **Incremental builds**: compilation state (source hash, last build timestamp) is stored in the local project DB.
4. **Output location**: compiled artifacts go to `assets/figures/` (PDF + optional SVG).
5. **Consumers reference artifacts**: Markdown notes use `![](assets/figures/name.svg)`, LaTeX notes use `\includegraphics{assets/figures/name}`.

---

## Architectural Rules

### MUST

- Complex diagrams **MUST be standalone `.tex` files**, not inline TikZ in documents.
- TikZ source **MUST NOT be embedded** directly in Markdown notes.
- Markdown notes **MUST reference rendered artifacts** (PDF/SVG), not TikZ source.
- TikZ styles **MUST use** shared style definitions from `shared/sty/VectorPGF.sty`.

### SHOULD

- Diagrams **SHOULD include** commented YAML metadata (id, tags, description).
- The `tikz build` command **SHOULD be incremental** (skip unchanged sources).
- SVG output **SHOULD be generated** for Markdown/Obsidian preview compatibility.

### MAY

- A `tikz watch` mode **MAY be implemented** for live development.
- ITEP symlinks (`lect/svg/`, `img/`) **MAY link** to compiled TikZ assets.

---

## Implementation Notes

- `assets/tikz/` directory convention per project.
- Existing `SetCommands.sty` has `\executeiffilenewer` (LuaTeX) for conditional SVG compilation — this pattern can be reused.
- Build state stored in local `slipbox.db` (new `TikzAsset` table: filename, source_hash, last_build).
- CLI: `workflow tikz build`, `workflow tikz list`.

---

## Impact on AI Coding Agents

- Never embed complex TikZ inline in Markdown or document `.tex` files.
- When creating diagrams, generate standalone `.tex` files in `assets/tikz/`.
- Reference compiled artifacts, not source files.
- Use `VectorPGF.sty` styles for consistency.

---

## Consequences

### Benefits

- Diagrams reusable across notes, exercises, slides, and Markdown
- Incremental builds save compilation time
- Obsidian preview compatibility via SVG

### Costs

- Additional build step in the workflow
- Two-file convention (source + compiled artifact)

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
