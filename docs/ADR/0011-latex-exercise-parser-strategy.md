---
adr: 0011
title: "LaTeX Exercise Parser Strategy: Brace-Aware Extraction"
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - exercises
  - parsing
  - latex
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "Zettelkasten/0005"
  - "Zettelkasten/0009"
---

## Context

The exercise parser must extract structured content from `.tex` files that use existing macros (`\question`, `\qpart`, `\pts`, `\rightoption`) and new macros (`\qfeedback`, `\qdiagram`). The challenge is that LaTeX macros have brace-delimited arguments that can nest arbitrarily:

```latex
\question{
  Given a sphere of radius $r$ with charge distribution
  $\rho(r) = \frac{Q}{4\pi r^{2}}$, find the electric field.
  \includegraphics[width=0.5\textwidth]{img/gauss-sphere.pdf}
  \begin{enumerate}[a)]
    \qpart{Determine $\vec{E}$ inside the sphere. \pts{5}}{
      Use Gauss's law: $\oint \vec{E} \cdot d\vec{A} = \frac{Q_{enc}}{\epsilon_{0}}$
    }
    \qpart{\rightoption Determine $\vec{E}$ outside the sphere. \pts{5}}{
      Apply $E = \frac{Q}{4\pi\epsilon_{0}r^{2}}$
    }
  \end{enumerate}
}{
  \textbf{General solution notes:} The key insight is symmetry.
}
```

A naive regex like `\\question\{(.*?)\}\{(.*?)\}` fails on nested braces.

### Macro Semantics (Existing)

Understanding the exact semantics of each macro is critical for correct parsing:

**`\question{stem}{solution}`**

- First argument: the **stem** — the question text itself, including any images, diagrams, or sub-parts (`\qpart`). This is what the student sees.
- Second argument: the **solution** — shown only when the `solutions` boolean is true. If the question has no parts, the full answer goes here. If it has parts, this may contain general solution notes or be empty.

**`\qpart{instruction}{solution}`**

- First argument: the **specific instruction** for this part. May or may not include points (`\pts{n}`). This is the sub-question text.
- Second argument: the **solution** for this specific part. Shown only when `solutions` boolean is true.

**`\pts{n}`** — point annotation, appears inside `\qpart` first argument or standalone. The `n` is the numeric point value.

**`\rightoption`** — a presence flag (no arguments). When it appears inside a `\qpart`'s first argument, it marks that option as the correct answer. In test mode, it renders as a blue checkmark (✓) only when `solutions` is true.

**`\exa[ch]{num}`** — exercise numbering. Optional first argument `ch` overrides chapter number, mandatory `num` sets exercise number within chapter.

### Options Considered

**Option A: Full LaTeX parser (e.g., TexSoup, pylatexenc)**

- Pro: Handles all LaTeX syntax correctly
- Con: Heavy dependency for a focused use case
- Con: pylatexenc is unmaintained; TexSoup has edge cases with math mode

**Option B: Brace-counting extractor (selected)**

- Pro: Zero dependencies — pure Python
- Pro: Focused on the exact macros we need
- Pro: Simple to understand, test, and debug
- Pro: Handles nested braces correctly via a stack/counter
- Con: Does not understand LaTeX semantics (e.g., `\{` as escaped brace)
- Con: Must handle edge cases manually (comments, verbatim)

**Option C: PEG grammar (e.g., parsimonious, lark)**

- Con: Overkill — we're extracting ~7 known macros, not parsing arbitrary LaTeX

---

## Decision

**Option B: Brace-counting extractor.**

The core parsing primitives live in `workflow.latex` (ADR-0009). The exercise-specific parser in `workflow.exercise.parser` uses those primitives to extract known macros.

### Core Algorithm (in `workflow.latex.braces`)

```python
def extract_brace_arg(text: str, start: int) -> tuple[str, int]:
    """Extract content between matched braces starting at position start.

    Returns (content, end_position). Handles nested braces.
    Skips braces preceded by backslash (escaped).
    """
    depth = 0
    i = start
    # Find opening brace
    while i < len(text) and text[i] != '{':
        i += 1
    content_start = i + 1
    depth = 1
    i += 1
    while i < len(text) and depth > 0:
        if text[i] == '{' and text[i-1] != '\\':
            depth += 1
        elif text[i] == '}' and text[i-1] != '\\':
            depth -= 1
        i += 1
    return text[content_start:i-1], i


def extract_macro_args(text: str, macro_name: str, n_args: int) -> list[tuple[list[str], int]]:
    """Find all occurrences of \\macro_name and extract n_args brace arguments.

    Returns list of (args, end_position) tuples.
    """
```

### Three-Pass Architecture

**Pass 1 — Metadata**: Extract commented YAML block (`^% ---` to `^% ---`) → `ExerciseMetadata` (reuse validation schema). Also extract `status` if present.

**Pass 2 — Structure**: Extract `\question{stem}{solution}` as two raw strings. Within the stem, extract all `\qpart{instruction}{solution}` pairs. Detect `\rightoption` presence within each `\qpart` first argument.

**Pass 3 — Annotations**: From the extracted content, pull:

- `\pts{n}` → `default_grade`
- `\qfeedback{text}` → feedback override
- `\qdiagram{id}` → TikZ asset reference
- `\includegraphics[...]{path}`, `\inputsvg{...}{...}{path}` → image references
- `\exa[ch]{num}` → exercise numbering context

### Parse Output

```python
@dataclass(frozen=True)
class ParsedOption:
    label: str              # a, b, c, d...
    instruction: str        # raw LaTeX of the \qpart first argument
    solution: str           # raw LaTeX of the \qpart second argument
    is_correct: bool        # True if \rightoption was present
    points: float | None    # from \pts{n} if present

@dataclass(frozen=True)
class ParsedExercise:
    metadata: ExerciseMetadata | None  # from commented YAML (None if absent)
    status: str                        # placeholder | in_progress | complete
    stem: str                          # raw LaTeX of \question first argument
    solution: str                      # raw LaTeX of \question second argument
    options: list[ParsedOption]        # from \qpart entries (empty for non-multichoice)
    feedback: str | None               # from \qfeedback if present
    default_grade: float | None        # from \pts if present
    diagram_id: str | None             # from \qdiagram if present
    image_refs: list[str]              # paths from \includegraphics, \inputsvg
    exercise_number: tuple[int | None, int] | None  # (chapter, number) from \exa

@dataclass(frozen=True)
class ParseResult:
    exercise: ParsedExercise | None    # None if file is not a valid exercise
    warnings: list[str]                # non-fatal issues
    errors: list[str]                  # fatal issues (missing \question, etc.)
    source_path: str                   # path to the .tex file
```

### Edge Cases

| Case                                 | Handling                                                              |
| ------------------------------------ | --------------------------------------------------------------------- |
| Nested `{}` in math                  | Brace counter tracks depth correctly                                  |
| `\{` escaped braces                  | Skip when preceded by `\`                                             |
| `% comment` lines                    | Strip before macro extraction (preserve in YAML block)                |
| Missing metadata                     | `ParseResult.warnings` += "no YAML metadata found"                    |
| Missing `\question`                  | `ParseResult.errors` += "no \\question macro found"                   |
| Multiple `\qpart`                    | Accumulate as `ParsedOption` list with labels a, b, c...              |
| `\qpart` without `\rightoption`      | `is_correct = False`                                                  |
| `\qpart` with `\rightoption`         | `is_correct = True`                                                   |
| Placeholder file (template only)     | Detected by absence of content in stem; `status = "placeholder"`      |
| `\pts` inside `\qpart` vs standalone | Extract from `\qpart` first arg if nested, or from stem if standalone |
| Images in stem or options            | Detected and added to `image_refs` list                               |

---

## Architectural Rules

### MUST

- Parser **MUST NOT** depend on external LaTeX parsing libraries.
- Brace-counting primitives **MUST** live in `workflow.latex.braces`, not in `workflow.exercise`.
- Parser **MUST** handle nested braces via counting, not regex.
- Parser **MUST** return a `ParseResult` with warnings/errors — never raise exceptions for malformed files.
- Parser **MUST** detect `\rightoption` within `\qpart` first argument to determine correct answers.
- Commented YAML extraction **MUST** reuse `ExerciseMetadata` from `workflow.validation.schemas`.

### SHOULD

- Parser **SHOULD** strip `%` comment prefixes before YAML parsing.
- Parser **SHOULD** preserve raw LaTeX in all extracted text (no interpretation).
- Parser **SHOULD** handle files with no metadata block (warn, extract content only).
- Parser **SHOULD** detect image references for `has_images` / `image_refs` population.
- Parser **SHOULD** infer `status` from content: no stem content → `placeholder`, partial content → `in_progress`, metadata + stem + solution → `complete`.

### MUST NOT

- Parser **MUST NOT** attempt to interpret LaTeX beyond macro extraction.
- Parser **MUST NOT** modify the source `.tex` file.

---

## Consequences

### Benefits

- Zero dependencies — pure Python, easy to test
- Shared brace-counting in `workflow.latex` benefits tikz and future modules
- `ParseResult` with warnings enables graceful degradation
- Status inference from content aligns with the file lifecycle model (ADR-0010)

### Costs

- `\{` and `\}` edge cases require careful handling
- Verbatim environments containing braces could confuse the counter (rare in exercises)
- Not reusable as a general LaTeX parser (by design)

---

## Status

**Accepted**

---

## Change Log

| Date       | Change                                                                                                            |
| ---------- | ----------------------------------------------------------------------------------------------------------------- |
| 2026-03-25 | Initial ADR                                                                                                       |
| 2026-03-25 | Rev 2: Correct \question/\qpart semantics, add image detection, status inference, shared workflow.latex reference |
