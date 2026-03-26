---
adr: LZK-0003
title: "Note Reference System: IDs, Cross-References, and Regex Patterns"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - latexzettel
  - references
  - regex
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LZK-0000"
  - "0001"
  - "0002"
---

## Context

The Zettelkasten method depends on dense cross-referencing between notes. The system must:

1. Assign unique, stable references to each note
2. Detect cross-references in both Markdown and LaTeX
3. Track citations to bibliography entries
4. Enable navigation between connected notes
5. Support multiple reference formats (LaTeX macros, wiki-links, standard `\ref`)

---

## Decision

**A centralized regex-based reference extraction system** in `infra/regexes.py`, with references stored in the `Note` model.

### Reference ID Format

Notes use a date-prefixed reference format:

```
YYYYMMDD-topic-subtopic
```

Examples:
- `20260326-gauss-law`
- `20260320-classical-mechanics-lagrangian`
- `lit-serway2019` (literature notes use `lit-` prefix)

The reference is stored in `Note.reference` and used as the stable identifier across formats:
- LaTeX: `\excref{20260326-gauss-law}` or `\exhyperref[20260326-gauss-law]{Gauss's Law}`
- Markdown: `[[20260326-gauss-law]]` or `[[20260326-gauss-law|Gauss's Law]]`

### Regex Patterns (`infra/regexes.py`)

10+ compiled patterns for reference extraction:

| Pattern | Matches | Used By |
|---------|---------|---------|
| `EXCREF_RE` | `\excref{id}` and `\excref[label]{id}` | LaTeX cross-references |
| `EXHYPERREF_RE` | `\exhyperref[id]{text}` | LaTeX hyperlinked references |
| `LABEL_RE` | `\label{name}` | LaTeX label definitions |
| `REF_RE` | `\ref{name}`, `\eqref{name}` | LaTeX reference usage |
| `CITE_RE` | `\cite{key}`, `\cite{k1,k2}` | BibTeX citations |
| `WIKILINK_RE` | `[[id]]`, `[[id\|text]]` | Markdown wiki-links |
| `INPUT_RE` | `\input{path}` | File inclusion tracking |
| `INCLUDE_RE` | `\include{path}` | File inclusion tracking |
| `SECTION_RE` | `\section{title}`, `\subsection{...}` | Document structure |
| `NOTE_FILENAME_RE` | `YYYYMMDD-*.tex` or `YYYYMMDD-*.md` | Note file detection |

### Reference Resolution

When a note references another:

1. **LaTeX**: `\excref{20260326-gauss-law}` → look up `Note.reference == "20260326-gauss-law"` → resolve to file path
2. **Markdown**: `[[20260326-gauss-law]]` → same lookup → optionally render as hyperlink
3. **Citation**: `\cite{serway2019}` → look up in BibEntry → track in Citation table

### Database Storage

References are tracked in three tables (LocalBase/slipbox.db):

```
Note
    reference: str (unique)    # e.g., "20260326-gauss-law"
    filename: str              # e.g., "20260326-gauss-law.tex"

Citation
    note_id → Note             # which note cites
    citationkey: str           # which bibliography entry

Link
    note_id → Note             # source note
    label_id → Label           # target (via label)

Label
    note_id → Note             # which note defines the label
    label: str                 # label name
```

### texnote.cls Macros

```latex
% Cross-reference to another note (defined in texnote.cls)
\newcommand{\excref}[2][]{%
  \ifthenelse{\isempty{#1}}{%
    \hyperref[zk:#2]{\textit{→ #2}}%
  }{%
    \hyperref[zk:#2]{\textit{→ #1}}%
  }%
}

% Hyperlinked reference with custom text
\newcommand{\exhyperref}[2][]{%
  \hyperref[#1]{\textit{#2}}%
}
```

---

## Architectural Rules

### MUST

- Note references **MUST** be unique within a project (enforced by DB constraint).
- References **MUST** be stable — once assigned, never change (rename creates a redirect).
- All regex patterns **MUST** be compiled at module level (not per-call).
- Citation extraction **MUST** handle multi-key `\cite{a,b,c}` by splitting on commas.

### SHOULD

- References **SHOULD** use date-prefix format `YYYYMMDD-topic` for chronological sorting.
- Literature notes **SHOULD** use `lit-{bibkey}` format.
- Wiki-links **SHOULD** support display text: `[[id|display]]`.

### MUST NOT

- Regex extraction **MUST NOT** match inside LaTeX comments (`%` lines).
- Reference resolution **MUST NOT** crash on dangling references — warn instead.

---

## Consequences

### Benefits

- Centralized regex patterns prevent duplication across modules
- Date-prefixed IDs enable chronological discovery
- Same reference works in both Markdown and LaTeX
- Link/Citation/Label tables enable graph analysis

### Costs

- Regex-based extraction can miss edge cases (nested macros, verbatim environments)
- Two macro systems coexist: `\excref` (latexzettel) and `\zlink` (proposed in ADR-0014)
- Reference format is convention-based, not enforced by the system

---

## Status

**Accepted** — documents existing reference system

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
