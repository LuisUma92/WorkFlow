---
adr: "0010"
title: "CentredPage — Full-page centered content command"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - Presentation
  - Visual flow control
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LATEX-STY/0000"
  - "LATEX-STY/0001"
  - "LATEX-STY/0002"
---

## Context

A reusable mechanism is needed to generate dedicated pages whose primary and
secondary content are **centered both vertically and horizontally relative to the
full page**, not just the text area.

Requirements:

- A **high-level command** (not an environment)
- Support for **flexible inline LaTeX content**
- **Footnote compatibility**
- A **configurable API** (colors, fonts, spacing, alignment)
- Avoid fragile overlay-based solutions (e.g. TikZ `current page.center`)
- Extensible base for future "page block" variants

Expected use cases:

- `{Title} []` — title-only page
- `{Title} [Subtitle]` — title with subtitle
- `{Logo} [Title]` — logo with title
- `{Title} [Epigraph¹]` — title with footnoted epigraph
- `{Concept} [Definition¹]` — concept with footnoted definition

---

## Decision

`\CentredPage` is defined as a **`\NewDocumentCommand`** that generates a
full page, centering its content via **controlled vertical flow with `\vbox`**,
not absolute positioning.

### Signature

```latex
\NewDocumentCommand{\CentredPage}{s O{} m o}{...}
```

| Arg | Spec | Meaning |
|-----|------|---------|
| `*` | `s` | Star variant: keeps current page style |
| `[keys]` | `O{}` | Optional l3keys configuration |
| `{primary}` | `m` | Mandatory primary content |
| `[secondary]` | `o` | Optional secondary content |

Default behavior (no star): applies `\thispagestyle{empty}`.

### Centering model

```latex
\makebox[\paperwidth][c]{%
  \vbox to \paperheight{%
    \vfill
    <content>
    \vfill
    \vspace*{<v-offset>}  % positive = shifts content upward
  }
}
```

Centering is relative to `\paperwidth`/`\paperheight`, independent of margins.
Content width uses `\textwidth`, respecting the document's lateral margins.

### Content structure

```latex
\vbox{
  <alignment>
  \textcolor{<primary-color>}{<primary-font> <primary>}\par
  \vspace{<block-sep>}
  \textcolor{<secondary-color>}{<secondary-font> <secondary>}\par
}
```

Colors are applied via `\textcolor` to **isolate** each block — colors do not
leak to footnotes or other elements.

### l3keys configuration

| Key | Type | Default |
|-----|------|---------|
| `primary-color` | color | `black` |
| `secondary-color` | color | `gray` |
| `primary-font` | font cmd | `\bfseries\Large` |
| `secondary-font` | font cmd | `\normalfont\large` |
| `line-spread` | real | `1.0` (via `\linespread`) |
| `block-sep` | dimension | `1em` |
| `content-width` | dimension | `\textwidth` |
| `v-offset` | dimension | `0pt` (positive = upward) |
| `align` | choice | `centering` |

Alignment accepts: `centering` (default), `raggedright`, `raggedleft`.

### Setup command

`\CentredPageSetup{key=value}` sets global defaults for all subsequent
`\CentredPage` invocations.

### Usage examples

```latex
% Title-only page (empty page style)
\CentredPage{Introduction}

% Title with subtitle, custom colors
\CentredPage[primary-color=blue]{Chapter One}[A Fresh Start]

% Star variant: keep headers/footers
\CentredPage*{Appendix Title}

% Full customization
\CentredPage[
  primary-font=\bfseries\Huge,
  secondary-font=\itshape\large,
  align=raggedright,
  block-sep=2em
]{Main Title}[Subtitle text]
```

### Supported content

**Allowed:** inline text, LaTeX commands, multiple paragraphs (`\par`),
manual line breaks (`\\[<dim>]`), inline images (`\includegraphics`),
footnotes (`\footnote`; in complex cases use `\footnotemark`+`\footnotetext`).

**Not supported (by contract):** float environments (`figure`, `table`).

---

## Architectural Rules

### MUST

- `\CentredPage` **MUST** center content relative to `\paperwidth`/`\paperheight`.
- The command **MUST** use `\NewDocumentCommand` with `xparse` argument spec `{s O{} m o}`.
- Configuration **MUST** use `l3keys` for all key–value parameters.
- Colors **MUST** be applied via `\textcolor`, not `\color`, to isolate each block.

### SHOULD

- The star variant **SHOULD** preserve the current page style (headers/footers).
- Default page style (non-star) **SHOULD** be `empty`.
- `\CentredPageSetup` **SHOULD** be provided for setting global defaults.

### MAY

- Future variants (`\QuotePage`, `\SectionDivider`, `\ConceptPage`) **MAY** be
  built on the same centering model.

---

## Implementation Notes

- **File location:** defined inside `shared/sty/SetCommands.sty` (ADR 0002).
  No separate `.sty` file — this is a shared command, not a standalone package.
- **LaTeX3 dependency:** requires `expl3`, `xparse`, and `l3keys2e`.
  These are part of the LaTeX kernel since TeX Live 2020-10-01.
- **Color dependency:** requires `xcolor` (loaded by `SetFormat.sty`, ADR 0000).
  Colors applied via `\textcolor` for isolation (no leaking to footnotes).
- **Line spread:** implemented with `\linespread{<value>}\selectfont` inside
  `\begingroup...\endgroup`. No dependency on `setspace` or other packages.
- No dependency on TikZ or any overlay/positioning package.

---

## Consequences

### Benefits

- Robust, extensible design based on standard TeX vertical flow
- Clear, semantic API with sensible defaults
- Broad class compatibility
- Fine-grained layout control via l3keys

### Costs

- Does not support float environments inside the centered page
- Footnotes not 100% guaranteed in all edge cases
- Requires LaTeX kernel ≥ 2020-10-01

---

## Alternatives Considered

### TikZ overlay (`current page.center`)

Rejected because:

- Fragile structural positioning
- Poor footnote compatibility
- Limits content richness (no paragraph breaks, limited nesting)

The `\vbox`-based approach is more robust and fully compatible with the TeX
page-building model.

---

## Compatibility / Migration

Supported document classes:

- `article`, `report`, `book`
- `memoir` (functional compatibility, no deep integration)
- `beamer` (content centering works; `\thispagestyle` is a no-op in beamer,
  so the star variant has no effect)

No migration required — this is a new command with no predecessor.

---

## Status

**Accepted**

---

## Change Log

| Date       | Change          |
| ---------- | --------------- |
| 2026-03-20 | Initial version                              |
| 2026-03-22 | Clarify v-offset, color isolation, host file |
