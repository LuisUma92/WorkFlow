---
adr: 0012
title: "Moodle XML Export with LaTeX Normalization"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - exercises
  - moodle
  - export
  - latex
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "0005"
  - "0009"
  - "0010"
  - "0011"
---

## Context

Exercises authored in LaTeX need to be exportable to Moodle XML for online assessment. The critical constraint is that **Moodle does not know the custom LaTeX commands** defined in `shared/sty/`:

- `\vc{E}` → `\vec{\symbf{E}}` (custom vector notation)
- `\scrp{enc}` → `_{\mbox{\scriptsize{enc}}}` (subscript helper)
- `\ncm{2}{H}` → `^{2}\text{H}` (nuclear notation)
- Colors defined in `SetColors.sty`
- Any other project-specific macros

Additionally, the user does not control which MathJax libraries or TeX filters are enabled on institutional Moodle instances (UCR, UFide, UCIMED). Relying on MathJax to understand custom commands is not viable.

**Therefore: LaTeX content must be translated to basic, standard LaTeX before export.** Only standard LaTeX commands that any MathJax installation understands should appear in the exported XML.

### Options Considered

**Option A: Raw LaTeX in CDATA with MathJax filter** (original proposal)
- Pro: Simple, zero conversion
- Con: Custom macros (`\vc`, `\scrp`, etc.) won't render — **deal-breaker**
- Con: Assumes institutional MathJax config — not under user's control

**Option B: Full LaTeX-to-HTML conversion (pandoc, make4ht)**
- Pro: Best visual fidelity
- Con: Heavy external dependency
- Con: Fragile for math-heavy content

**Option C: LaTeX normalization + CDATA export (selected)**
- Pro: Resolves custom macros to standard LaTeX before export
- Pro: Standard LaTeX works with any MathJax installation
- Pro: No external dependencies — normalization is a text transform
- Pro: Preserves math fidelity (all standard LaTeX math renders correctly)
- Con: Must maintain a normalization map for each custom macro
- Con: Some formatting (non-math custom macros) may be simplified

---

## Decision

**Option C: Normalize custom LaTeX to standard form, then export as CDATA.**

### Two-Phase Export Pipeline

```
.tex file → Parse (ADR-0011) → Normalize (expand custom macros) → Moodle XML
```

**Phase 1 — Normalization** (`workflow.latex.normalize`):

Expand all custom macros from `shared/sty/` to their standard LaTeX equivalents. The normalization map is derived directly from the `.sty` files:

```python
# Auto-derived from SetCommands.sty, PartialCommands.sty, etc.
MACRO_MAP: dict[str, MacroExpansion] = {
    # SetCommands.sty
    r"\vc":    MacroExpansion(args=1, template=r"\vec{{\symbf{{{0}}}}}"),
    r"\scrp":  MacroExpansion(args=1, template=r"_{{\mbox{{\scriptsize{{{0}}}}}}}"),
    r"\nc":    MacroExpansion(args=2, template=r"$^{{{0}}}${1}"),
    r"\ncm":   MacroExpansion(args=2, template=r"^{{{0}}}\text{{{1}}}"),
    r"\then":  MacroExpansion(args=0, template=r"="),
    # PartialCommands.sty
    r"\pts":   MacroExpansion(args=1, template=r"({0} pts.)"),
    r"\upt":   MacroExpansion(args=0, template=r"(1 pt.)"),
    r"\uptcu": MacroExpansion(args=0, template=r"(1 pt. c/u.)"),
    r"\ptscu": MacroExpansion(args=1, template=r"({0} pts. c/u.)"),
    # Colors — strip color commands, keep content
    r"\textcolor": MacroExpansion(args=2, template=r"{1}"),  # drop color, keep text
}
```

The normalization step also:
- Converts math delimiters: `$...$` → `\(...\)`, `$$...$$` → `\[...\]`
- Strips exercise-structural macros (`\question`, `\qpart`, `\rightoption`, `\consolidatePoints`) — these are already parsed
- Resolves `\symbf` → `\mathbf` (MathJax-compatible)
- Leaves standard LaTeX commands (`\frac`, `\vec`, `\text`, `\begin{enumerate}`, etc.) unchanged

**Phase 2 — XML Generation** (`workflow.exercise.moodle`):

Use `xml.etree.ElementTree` (stdlib). Content goes into CDATA sections.

### Mapping Rules

| Source | Moodle XML Target |
|---|---|
| `\question` stem (normalized) | `<questiontext format="html"><text><![CDATA[...]]></text></questiontext>` |
| `\question` solution (normalized) | `<generalfeedback format="html"><text><![CDATA[...]]></text></generalfeedback>` |
| `\qpart` instruction (normalized) | `<answer fraction="F"><text><![CDATA[...]]></text></answer>` |
| `\qpart` solution (normalized) | `<answer>...<feedback><text><![CDATA[...]]></text></feedback></answer>` |
| `\rightoption` on `\qpart` | Sets `fraction="100"` on the corresponding `<answer>` |
| `\pts{n}` | `<defaultgrade>n</defaultgrade>` |
| `\qfeedback{text}` (normalized) | `<generalfeedback>` (overrides solution-based feedback) |
| Commented YAML tags | `<tags><tag><text>value</text></tag></tags>` |
| `exercise_id` | `<idnumber>exercise_id</idnumber>` |

### Image Handling

When `has_images` is true (ADR-0010), the exporter must:
1. Resolve image paths relative to the exercise file location
2. Read image files and base64-encode them
3. Embed as `<file>` elements in the Moodle XML question
4. Replace `\includegraphics` references with `<img>` tags in the CDATA content

```xml
<question type="multichoice">
  <questiontext format="html">
    <text><![CDATA[... <img src="@@PLUGINFILE@@/gauss-sphere.png" /> ...]]></text>
    <file name="gauss-sphere.png" path="/" encoding="base64">iVBORw0KGgo...</file>
  </questiontext>
</question>
```

For TikZ diagrams referenced via `\qdiagram{id}`, the exporter resolves the compiled SVG/PNG from the tikz asset pipeline (Phase 2) and embeds it the same way.

### Question Type Mapping

| YAML `type` | Moodle `<question type="...">` | Notes |
|---|---|---|
| `multichoice` | `multichoice` | Options from `\qpart` entries; `\rightoption` marks correct |
| `essay` | `essay` | Stem only; solution as grader guidance |
| `shortanswer` | `shortanswer` | Solution text becomes expected answer |
| `numerical` | `numerical` | Solution parsed as number; default tolerance |
| `truefalse` | `truefalse` | Two options; `\rightoption` marks correct |

### Output Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>phys-gauss-001</text></name>
    <questiontext format="html">
      <text><![CDATA[
        Given a sphere of radius \(r\) with charge distribution
        \(\rho(r) = \frac{Q}{4\pi r^{2}}\), find the electric field.
      ]]></text>
    </questiontext>
    <generalfeedback format="html">
      <text><![CDATA[The key insight is symmetry.]]></text>
    </generalfeedback>
    <defaultgrade>10</defaultgrade>
    <penalty>0.3333333</penalty>
    <single>true</single>
    <shuffleanswers>1</shuffleanswers>
    <answer fraction="0" format="html">
      <text><![CDATA[(5 pts.) Determine \(\vec{\mathbf{E}}\) inside the sphere.]]></text>
      <feedback><text><![CDATA[Use Gauss's law...]]></text></feedback>
    </answer>
    <answer fraction="100" format="html">
      <text><![CDATA[(5 pts.) Determine \(\vec{\mathbf{E}}\) outside the sphere.]]></text>
      <feedback><text><![CDATA[Apply \(E = \frac{Q}{4\pi\epsilon_{0}r^{2}}\)]]></text></feedback>
    </answer>
    <tags>
      <tag><text>physics</text></tag>
      <tag><text>electrostatics</text></tag>
    </tags>
  </question>
</quiz>
```

Note how `\vc{E}` has been normalized to `\vec{\mathbf{E}}` — standard LaTeX that any MathJax instance can render.

---

## Architectural Rules

### MUST

- All custom macros from `shared/sty/` **MUST** be expanded to standard LaTeX before XML generation.
- `workflow.latex.normalize` **MUST** own the macro expansion map, derived from `.sty` file definitions.
- XML generation **MUST** use `xml.etree.ElementTree` — no string templating.
- Math delimiters **MUST** be converted: `$...$` → `\(...\)`, `$$...$$` → `\[...\]`.
- Content **MUST** be wrapped in `<![CDATA[...]]>`.
- Each exercise **MUST** have an `<idnumber>` matching its `exercise_id` from YAML.
- Images **MUST** be base64-encoded and embedded as `<file>` elements when present.

### SHOULD

- Exporter **SHOULD** validate that multichoice questions have at least one correct answer.
- Exporter **SHOULD** warn if `default_grade` is missing.
- Exporter **SHOULD** support filtering by tag, taxonomy, difficulty, and status (only `complete` exercises).
- The normalization map **SHOULD** be auto-derivable from `.sty` files where possible, with manual overrides for complex macros.
- Exporter **SHOULD** warn when encountering an unknown custom macro (not in the normalization map).

### MUST NOT

- Exporter **MUST NOT** assume institutional MathJax configuration.
- Exporter **MUST NOT** leave custom macros (`\vc`, `\scrp`, etc.) in the exported XML.
- Exporter **MUST NOT** depend on external tools (pandoc, make4ht) at export time.
- Exporter **MUST NOT** modify the source `.tex` files.

---

## Consequences

### Benefits

- Works on **any** Moodle instance with basic MathJax — no institutional config dependency
- Custom macros are properly expanded, not silently dropped
- Images embedded directly in XML — no external references to break
- Normalization map serves as living documentation of all custom macros

### Costs

- Must maintain `MACRO_MAP` when `.sty` files change (mitigated: map derived from source)
- Complex macros with conditional logic (e.g., `\exa` with `\ifthenelse`) cannot be mechanically expanded — these are structural macros already stripped by the parser
- First implementation requires auditing all macros in `shared/sty/` to build the initial map

### Open Question

- **LaTeX formatting guide**: A reference document mapping each custom macro to its standard equivalent would help both the normalization code and manual editing. Should this live in `shared/sty/MACRO-REFERENCE.md` or be auto-generated from the normalization map?

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
| 2026-03-25 | Rev 2: Replace raw-CDATA approach with LaTeX normalization pipeline, add image embedding, custom macro expansion map, remove MathJax dependency assumption |
