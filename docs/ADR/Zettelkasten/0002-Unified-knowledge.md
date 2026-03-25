---
adr: 0002
title: "Markdown as Canonical Knowledge Layer"
status: Accepted
date: 2026-03-24
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - knowledge-management
  - markdown
  - obsidian
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "Zettelkasten/0001"
  - "Zettelkasten/0003"
---

## Context

ADR-0001 defines a LaTeX-based note semantic layer. However, LaTeX is optimal for rendering, not for semantic storage or lightweight note-taking. Requirements emerged for:

- Obsidian-compatible note-taking workflow
- Bidirectional wiki-link support (`[[Note Name]]`, `[[Note#label]]`)
- YAML frontmatter for structured metadata
- Automated conversion between Markdown and LaTeX via Pandoc

Markdown provides superior semantic expressiveness and tooling ecosystem for knowledge representation. LaTeX remains the output format for publication.

---

## Decision

**Markdown (`.md`) is the primary source of truth for knowledge.** LaTeX is a derived output format.

1. **Knowledge notes** are authored in Markdown with YAML frontmatter.
2. **Bidirectional linking** uses wiki-link syntax (`[[...]]`), parsed by CLI tooling.
3. **LaTeX output** is generated via Pandoc with custom filters and templates (already in `src/latexzettel/pandoc/`).
4. **Outputs are derived artifacts only** — PDF, slides, exams, Moodle XML. Outputs MUST NOT be treated as source of truth.

---

## Architectural Rules

### MUST

- Knowledge **MUST be stored in Markdown (`.md`) files** with YAML frontmatter.
- Each note **MUST have a unique ID** in frontmatter.
- Wiki-links **MUST be the inter-note reference mechanism** in Markdown.
- CLI tooling **MUST handle Markdown→LaTeX conversion**.
- Outputs **MUST NOT be treated as canonical sources**.

### SHOULD

- Frontmatter **SHOULD be validated** against a defined schema.
- Notes **SHOULD be Obsidian-compatible** (standard wiki-links, YAML frontmatter).
- Naming conventions **SHOULD align** between notes, diagrams, and exercises.

### MAY

- Alternative export formats (HTML, JSON) **MAY be supported** in future.

---

## Implementation Notes

- Markdown notes live under `notes/md/` (per latexzettel config).
- Pandoc pipeline: `src/latexzettel/pandoc/` (filter.lua, template.tex, defaults.yaml).
- `sync_md` API converts Markdown → LaTeX and registers notes in the DB.
- `tex_to_md` API converts LaTeX → Markdown for migration.

---

## Impact on AI Coding Agents

- Treat Markdown as the canonical knowledge layer.
- Never generate LaTeX notes directly — generate Markdown and let the pipeline convert.
- Respect YAML frontmatter schemas.
- Maintain ID consistency between Markdown notes and the DB.

---

## Consequences

### Benefits

- Obsidian-compatible workflow
- Strong separation between semantics and rendering
- Rich tooling ecosystem (linters, editors, Obsidian plugins)

### Costs

- Dual-format system (Markdown + LaTeX)
- Pandoc dependency for conversion

---

## Compatibility / Migration

No breaking changes to ADR-0001. Existing LaTeX notes can be progressively migrated to Markdown via `tex_to_md`.

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                                        |
| ---------- | --------------------------------------------- |
| 2026-03-24 | Initial ADR (broad scope)                     |
| 2026-03-25 | Narrowed to Markdown knowledge layer only. Exercises, TikZ, DB, ORM moved to separate ADRs. Accepted. |
