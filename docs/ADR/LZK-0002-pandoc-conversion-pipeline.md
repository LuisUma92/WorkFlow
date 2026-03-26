---
adr: LZK-0002
title: "Pandoc Conversion Pipeline: Markdown ↔ LaTeX with Wiki-Link Support"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - latexzettel
  - pandoc
  - markdown
  - latex
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LZK-0000"
  - "0002"
---

## Context

ADR-0002 establishes Markdown as the canonical knowledge format. LaTeX is a derived output for PDF/slides/exams. A bidirectional conversion pipeline is needed:

- **Markdown → LaTeX**: For rendering notes to PDF, including in lecture documents, exporting to projects
- **LaTeX → Markdown**: For importing existing LaTeX notes into the Markdown-first workflow

Key challenges:
- Wiki-links (`[[note-id]]`) have no LaTeX equivalent — must be converted to `\excref`
- Theorem environments need special handling
- Custom macros from `shared/sty/` must survive round-trips
- Math must be preserved exactly

---

## Decision

**Pandoc with a Lua filter and Python preprocessor** for Markdown → LaTeX conversion.

### Pipeline

```
Markdown (.md)
    ↓
preprocess.py          # Convert [[wiki-links]] to pandoc-friendly format
    ↓
pandoc --filter         # Core conversion with custom filter
    ↓
filter.lua             # Handle theorem environments, references
    ↓
template.tex           # LaTeX template with \input for preamble
    ↓
LaTeX (.tex)
```

### Components

**`pandoc/preprocess.py`** — Pre-processes Markdown before Pandoc:
- Converts `[[note-id]]` wiki-links to `\excref{note-id}` (or `\hyperref[zk:note-id]{note-id}`)
- Handles `[[note-id|display text]]` with custom display
- Strips Obsidian-specific syntax that Pandoc doesn't understand

**`pandoc/filter.lua`** — Pandoc Lua filter:
- Converts theorem-like environments (Definition, Theorem, Proof, Example)
- Handles cross-references and citation formatting
- Preserves raw LaTeX blocks

**`pandoc/template.tex`** — LaTeX template:
- Includes `texnote.cls` document class
- Imports preamble from project config
- Sets up bibliography

**`pandoc/defaults.yaml`** — Pandoc defaults file:
```yaml
from: markdown+raw_tex+tex_math_dollars+yaml_metadata_block
to: latex
template: template.tex
lua-filter: filter.lua
```

### Reverse Pipeline (LaTeX → Markdown)

```
LaTeX (.tex)
    ↓
pandoc --from latex --to markdown
    ↓
Post-process: \excref{id} → [[id]]
    ↓
Markdown (.md)
```

The reverse pipeline is simpler — Pandoc handles most LaTeX → Markdown natively. Only `\excref` and custom macros need post-processing.

### API Integration

```python
# api/markdown.py
def sync_md(db, md_path: Path, project_root: Path) -> SyncResult:
    """Sync a Markdown note to the database and optionally compile to LaTeX."""

def tex_to_md(db, tex_path: Path, output_dir: Path) -> Path:
    """Convert a LaTeX note to Markdown, preserving references."""
```

---

## Architectural Rules

### MUST

- `[[wiki-link]]` **MUST** be converted to `\excref{note-id}` in LaTeX output.
- Math expressions **MUST** be preserved exactly during conversion.
- The pipeline **MUST** work with Pandoc 2.19+ (available in current distros).
- Raw LaTeX blocks in Markdown **MUST** pass through to the output unchanged.

### SHOULD

- Theorem environments **SHOULD** be converted to matching LaTeX environments.
- The filter **SHOULD** handle `\cite{key}` in both directions.
- The preprocessor **SHOULD** be idempotent (safe to run twice).

### MUST NOT

- The pipeline **MUST NOT** modify math content (equations, inline math).
- The conversion **MUST NOT** depend on `shared/sty/` macros being defined — output should compile with texnote.cls alone.

---

## Consequences

### Benefits

- Pandoc handles 90% of Markdown ↔ LaTeX conversion
- Lua filter is lightweight and fast
- Wiki-links enable Obsidian compatibility
- Bidirectional: notes can be authored in either format

### Costs

- Pandoc is a runtime dependency (~100MB)
- Lua filter maintenance for edge cases
- Round-trip fidelity is not perfect (some LaTeX constructs don't map cleanly)

---

## Status

**Accepted** — documents existing pipeline

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
