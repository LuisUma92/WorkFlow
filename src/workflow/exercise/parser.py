"""Exercise .tex file parser.

Extracts commented YAML metadata and LaTeX macro content from
exercise files using the brace-counting primitives in workflow.latex.

Three-pass architecture (ADR-0011):
  Pass 1 — Metadata: extract commented YAML block
  Pass 2 — Structure: extract \\question and \\qpart macros
  Pass 3 — Annotations: extract \\pts, \\qfeedback, \\qdiagram, images

See ADR-0011 for full design rationale.
"""

from __future__ import annotations

import re
from typing import TypedDict

from workflow.latex.braces import extract_macro_args
from workflow.latex.comments import extract_commented_yaml
from workflow.validation.schemas import (
    ExerciseMetadata,
    validate_exercise_metadata,
)

from workflow.exercise.domain import (
    ParsedExercise,
    ParsedOption,
    ParseResult,
)

__all__ = ["parse_exercise"]

# Regex patterns for image references
_IMAGE_PATTERNS = [
    re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}"),
    re.compile(r"\\inputsvg\s*\{[^}]*\}\s*\{([^}]+)\}\s*\{[^}]+\}"),
    re.compile(r"\\qdiagram\s*\{([^}]+)\}"),
]


def _extract_points(text: str) -> float | None:
    """Extract numeric value from \\pts{n} in text."""
    matches = extract_macro_args(text, "pts", 1)
    if not matches:
        return None
    try:
        # pts may have optional first arg: \pts[add]{5} — extract last arg
        raw = matches[0].args[0].strip()
        return float(raw)
    except (ValueError, IndexError):
        return None


def _extract_image_refs(text: str) -> list[str]:
    """Find all image file references in LaTeX text."""
    refs: list[str] = []
    for pattern in _IMAGE_PATTERNS:
        for m in pattern.finditer(text):
            refs.append(m.group(1).strip())
    return refs


def _has_rightoption(text: str) -> bool:
    """Check if \\rightoption appears in text."""
    matches = extract_macro_args(text, "rightoption", 0)
    return len(matches) > 0


def _infer_status(
    metadata: ExerciseMetadata | None,
    stem: str,
    solution: str,
) -> str:
    """Infer exercise status from content.

    - No meaningful stem content → placeholder
    - Has stem but missing metadata or solution → in_progress
    - Has metadata + stem + solution → complete
    """
    # Check if stem has real content (not just template placeholders)
    stem_stripped = stem.strip()
    if not stem_stripped or stem_stripped == "...":
        return "placeholder"

    if metadata is None or not solution.strip():
        return "in_progress"

    return "complete"


class _Annotations(TypedDict):
    default_grade: float | None
    feedback: str | None
    diagram_id: str | None
    image_refs: list[str]
    exercise_number: tuple[int | None, int] | None


def _extract_annotations(text: str, stem_raw: str) -> _Annotations:
    """Extract annotations from exercise text (Pass 3).

    Returns a TypedDict with keys: default_grade, feedback, diagram_id,
    image_refs, exercise_number.
    """
    result: _Annotations = {}  # type: ignore[typeddict-item]

    result["default_grade"] = _extract_points(stem_raw)

    feedback_matches = extract_macro_args(text, "qfeedback", 1)
    result["feedback"] = feedback_matches[0].args[0] if feedback_matches else None

    diagram_matches = extract_macro_args(text, "qdiagram", 1)
    result["diagram_id"] = (
        diagram_matches[0].args[0].strip() if diagram_matches else None
    )

    result["image_refs"] = _extract_image_refs(text)

    exercise_number: tuple[int | None, int] | None = None
    exa_matches = extract_macro_args(text, "exa", 1)
    if exa_matches:
        try:
            num = int(exa_matches[0].args[0].strip())
            exercise_number = (None, num)
        except ValueError:
            pass
    result["exercise_number"] = exercise_number

    return result


def parse_exercise(text: str, source_path: str = "") -> ParseResult:
    """Parse a .tex exercise file into structured domain objects.

    Parameters
    ----------
    text : str
        Full contents of the .tex file.
    source_path : str
        Path to the file (for diagnostics only).

    Returns
    -------
    ParseResult
        Parsed exercise with warnings/errors. Never raises exceptions.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # ── Pass 1: Metadata ─────────────────────────────────────────────
    yaml_data, remaining = extract_commented_yaml(text)

    metadata: ExerciseMetadata | None = None
    explicit_status: str | None = None

    if yaml_data is None:
        warnings.append("No YAML metadata block found")
    else:
        # Extract status before validation (not part of ExerciseMetadata)
        explicit_status = yaml_data.get("status")
        yaml_data = {k: v for k, v in yaml_data.items() if k != "status"}

        validated, validation_errors = validate_exercise_metadata(yaml_data)
        if validation_errors:
            for err in validation_errors:
                warnings.append(f"Metadata: {err}")
        else:
            metadata = validated

    # ── Pass 2: Structure ────────────────────────────────────────────
    question_matches = extract_macro_args(text, "question", 2)

    if not question_matches:
        errors.append("No \\question macro found — file is not a valid exercise")
        return ParseResult(
            exercise=None,
            warnings=tuple(warnings),
            errors=tuple(errors),
            source_path=source_path,
        )

    # Use the first \question found
    stem_raw, solution_raw = question_matches[0].args

    # Extract \qpart entries from within the stem
    qpart_matches = extract_macro_args(stem_raw, "qpart", 2)
    options: list[ParsedOption] = []

    for idx, qm in enumerate(qpart_matches):
        instruction, qsolution = qm.args
        label = chr(ord("a") + idx)
        is_correct = _has_rightoption(instruction)
        points = _extract_points(instruction)

        options.append(
            ParsedOption(
                label=label,
                instruction=instruction,
                solution=qsolution,
                is_correct=is_correct,
                points=points,
            )
        )

    # ── Pass 3: Annotations ──────────────────────────────────────────
    ann = _extract_annotations(text, stem_raw)

    # Status: explicit from YAML, or inferred
    if explicit_status and explicit_status in (
        "placeholder",
        "in_progress",
        "complete",
    ):
        status = explicit_status
    else:
        status = _infer_status(metadata, stem_raw, solution_raw)

    exercise = ParsedExercise(
        stem=stem_raw,
        solution=solution_raw,
        metadata=metadata,
        status=status,
        options=tuple(options),
        feedback=ann["feedback"],
        default_grade=ann["default_grade"],
        diagram_id=ann["diagram_id"],
        image_refs=tuple(ann["image_refs"]),
        exercise_number=ann["exercise_number"],
    )

    return ParseResult(
        exercise=exercise,
        warnings=tuple(warnings),
        errors=tuple(errors),
        source_path=source_path,
    )
