"""Pure domain types for parsed exercises.

All types are immutable (frozen dataclasses). They carry no DB or
I/O dependencies — pure data containers returned by the parser.

See ADR-0011 for ParseResult design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass

from workflow.validation.schemas import ExerciseMetadata


@dataclass(frozen=True)
class ParsedOption:
    """A single answer option extracted from a \\qpart macro."""

    label: str  # a, b, c, d...
    instruction: str  # raw LaTeX of \qpart first argument
    solution: str  # raw LaTeX of \qpart second argument
    is_correct: bool = False  # True if \rightoption was present
    points: float | None = None  # from \pts{n} if present


@dataclass(frozen=True)
class ParsedExercise:
    """Structured representation of a parsed exercise .tex file."""

    stem: str  # raw LaTeX of \question first arg
    solution: str  # raw LaTeX of \question second arg
    metadata: ExerciseMetadata | None = None  # from commented YAML (None if absent)
    status: str = "placeholder"  # placeholder | in_progress | complete
    options: tuple[ParsedOption, ...] = ()  # from \qpart entries
    feedback: str | None = None  # from \qfeedback if present
    default_grade: float | None = None  # from \pts if present (standalone)
    diagram_id: str | None = None  # from \qdiagram if present
    image_refs: tuple[str, ...] = ()  # paths from \includegraphics, \inputsvg
    exercise_number: tuple[int | None, int] | None = None  # (chapter, num) from \exa


@dataclass(frozen=True)
class ParseResult:
    """Container for parser output — exercise data plus diagnostics."""

    exercise: ParsedExercise | None = None  # None if file is not a valid exercise
    warnings: tuple[str, ...] = ()  # non-fatal issues
    errors: tuple[str, ...] = ()  # fatal issues
    source_path: str = ""  # path to the .tex file
