"""Exam assembly module.

Reads selected exercise .tex files and assembles them into an exam document
body. Per ADR-0010 the .tex file is the truth source — content is read from
disk at build time, never from the DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workflow.exercise.parser import parse_exercise
from workflow.exercise.selector import SelectionResult


@dataclass(frozen=True)
class ExamDocument:
    """An assembled exam document."""

    title: str
    content: str  # assembled LaTeX content (body only, no preamble)
    total_points: float
    exercise_count: int
    warnings: tuple[str, ...]


def _read_stem(source_path: str, exercise_id: str) -> tuple[str | None, str]:
    """Read .tex file and return (stem_text, warning_or_empty).

    Returns (None, warning_message) if the file is missing or unreadable.
    """
    path = Path(source_path)
    if not path.exists():
        return None, f"File missing for exercise '{exercise_id}': {source_path}"

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Cannot read '{exercise_id}': {exc}"

    result = parse_exercise(text, source_path=source_path)
    if result.exercise is None:
        return None, f"Parse failed for '{exercise_id}': " + "; ".join(result.errors)

    return result.exercise.stem, ""


def build_exam(
    selection: SelectionResult,
    *,
    title: str = "Exam",
    instructions: str = "",
) -> ExamDocument:
    """Assemble an exam document from selected exercises.

    Reads each selected exercise's .tex file (file-as-truth per ADR-0010),
    extracts the \\question stem, and assembles into a LaTeX document body.

    Does NOT add document preamble or \\begin{document} — just the exam body
    content (title, optional instructions, questions list with point annotations).
    """
    warnings: list[str] = list(selection.warnings)
    lines: list[str] = []
    total_points = 0.0
    exercise_count = 0

    # Header
    lines.append(f"% Exam: {title}")
    if instructions:
        lines.append(f"% Instructions: {instructions}")
        lines.append("")

    lines.append(r"\begin{questions}")

    for slot, exercises in selection.selected.items():
        for ex in exercises:
            stem, warn = _read_stem(ex.source_path, ex.exercise_id)
            if stem is None:
                warnings.append(warn)
                continue

            exercise_count += 1
            total_points += slot.points_per_item

            lines.append(
                rf"\question[{slot.points_per_item:g}]"
                f"  % {ex.exercise_id}"
            )
            # Include the raw stem content indented
            for stem_line in stem.splitlines():
                lines.append(f"  {stem_line}")
            lines.append("")

    lines.append(r"\end{questions}")

    return ExamDocument(
        title=title,
        content="\n".join(lines),
        total_points=total_points,
        exercise_count=exercise_count,
        warnings=tuple(warnings),
    )


__all__ = ["ExamDocument", "build_exam"]
