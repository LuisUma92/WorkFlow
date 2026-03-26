"""Moodle XML export for parsed exercises.

Converts ParsedExercise objects to Moodle XML <question> elements.
All LaTeX content is normalized (custom macros expanded, math delimiters
converted) before insertion.

See ADR-0012 for design rationale.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Sequence
from xml.etree.ElementTree import Element, SubElement, tostring

import warnings

from workflow.exercise.domain import ParsedExercise, ParsedOption
from workflow.latex.normalize import normalize, MacroRule


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FALLBACK_NAME = "unnamed-exercise"
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _set_text(parent: Element, tag: str, content: str, fmt: str = "html") -> Element:
    """Create <tag format=fmt><text>content</text></tag> under parent."""
    container = SubElement(parent, tag, {"format": fmt})
    text_elem = SubElement(container, "text")
    text_elem.text = content
    return container


def _infer_question_type(exercise: ParsedExercise) -> str:
    """Infer Moodle question type from exercise structure when metadata is absent."""
    if exercise.options:
        return "multichoice"
    return "essay"


def _embed_image(image_path: Path) -> tuple[str, str]:
    """Return (filename, base64_data) for an image file."""
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return image_path.name, data


def _attach_images(
    parent: Element, image_refs: tuple[str, ...], source_dir: Path | None
) -> None:
    """Embed images as <file encoding="base64"> children of parent."""
    resolved_source = source_dir.resolve() if source_dir is not None else None

    for ref in image_refs:
        ref_path = Path(ref)
        if not ref_path.is_absolute() and source_dir is not None:
            ref_path = source_dir / ref_path

        resolved = ref_path.resolve()

        # Path traversal guard: image must stay within source_dir
        if resolved_source is not None and not str(resolved).startswith(
            str(resolved_source)
        ):
            warnings.warn(f"Skipping image outside source_dir (path traversal): {ref}")
            continue

        if not resolved.exists():
            continue

        # Size guard: skip images larger than 10 MB
        if resolved.stat().st_size > _MAX_IMAGE_BYTES:
            warnings.warn(
                f"Skipping oversized image (>{_MAX_IMAGE_BYTES} bytes): {ref}"
            )
            continue

        name, data = _embed_image(resolved)
        file_elem = SubElement(
            parent, "file", {"name": name, "path": "/", "encoding": "base64"}
        )
        file_elem.text = data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def exercise_to_xml(
    exercise: ParsedExercise,
    *,
    source_dir: Path | None = None,
    macro_map: dict[str, MacroRule] | None = None,
) -> Element:
    """Convert a ParsedExercise to a Moodle XML <question> element.

    Parameters
    ----------
    exercise:
        The parsed exercise to convert.
    source_dir:
        Directory containing the exercise file; used to resolve image paths.
    macro_map:
        Custom macro expansion rules. Defaults to DEFAULT_MACRO_MAP.

    Returns
    -------
    Element
        A <question> element ready for serialization.
    """
    meta = exercise.metadata

    # Determine question type
    if meta is not None:
        q_type = meta.type
    else:
        q_type = _infer_question_type(exercise)

    question = Element("question", {"type": q_type})

    # <name>
    exercise_id = meta.id if meta is not None else _FALLBACK_NAME
    name_elem = SubElement(question, "name")
    name_text = SubElement(name_elem, "text")
    name_text.text = exercise_id

    # <idnumber>
    idnumber = SubElement(question, "idnumber")
    idnumber.text = exercise_id

    # <questiontext> — normalized stem
    norm_stem = normalize(exercise.stem, macro_map)
    qtext_container = _set_text(question, "questiontext", norm_stem)

    # Embed images in <questiontext>
    if exercise.image_refs:
        _attach_images(qtext_container, exercise.image_refs, source_dir)

    # <generalfeedback> — prefer \qfeedback, fall back to solution
    feedback_content = (
        exercise.feedback if exercise.feedback is not None else exercise.solution
    )
    _set_text(question, "generalfeedback", normalize(feedback_content, macro_map))

    # <defaultgrade>
    if exercise.default_grade is not None:
        grade_elem = SubElement(question, "defaultgrade")
        grade_elem.text = str(exercise.default_grade)

    # <penalty> and type-specific elements
    if q_type == "multichoice":
        penalty = SubElement(question, "penalty")
        penalty.text = "0.3333333"
        single = SubElement(question, "single")
        single.text = "true"
        shuffle = SubElement(question, "shuffleanswers")
        shuffle.text = "1"

    # <answer> elements
    _add_answers(question, exercise, q_type, macro_map)

    # <tags>
    if meta is not None and meta.tags:
        tags_elem = SubElement(question, "tags")
        for tag_value in meta.tags:
            tag_elem = SubElement(tags_elem, "tag")
            tag_text = SubElement(tag_elem, "text")
            tag_text.text = tag_value

    return question


def _add_answers(
    question: Element,
    exercise: ParsedExercise,
    q_type: str,
    macro_map: dict[str, MacroRule] | None,
) -> None:
    """Add <answer> elements to the question element based on type."""
    if q_type == "essay":
        return  # no answers for essay

    if q_type == "multichoice":
        _add_multichoice_answers(question, exercise.options, macro_map)
        return

    if q_type in ("shortanswer", "numerical"):
        # Single correct answer from solution
        answer_elem = SubElement(
            question, "answer", {"fraction": "100", "format": "html"}
        )
        text_elem = SubElement(answer_elem, "text")
        text_elem.text = normalize(exercise.solution, macro_map)
        return

    if q_type == "truefalse":
        _add_multichoice_answers(question, exercise.options, macro_map)
        return


def _add_multichoice_answers(
    question: Element,
    options: tuple[ParsedOption, ...],
    macro_map: dict[str, MacroRule] | None,
) -> None:
    """Add multichoice/truefalse <answer> elements."""
    n_correct = sum(1 for o in options if o.is_correct)
    # Edge case: if no option is marked correct, all fractions stay "0".
    # Moodle will accept the XML but the question will be ungraded — this is
    # intentional (don't crash, let the author fix the source file).
    # Fraction per correct answer (handles multiple-correct case)
    correct_fraction = "100" if n_correct <= 1 else str(round(100 / n_correct, 7))

    for opt in options:
        fraction = correct_fraction if opt.is_correct else "0"
        answer_elem = SubElement(
            question, "answer", {"fraction": fraction, "format": "html"}
        )
        text_elem = SubElement(answer_elem, "text")
        text_elem.text = normalize(opt.instruction, macro_map)
        if opt.solution:
            feedback_container = SubElement(answer_elem, "feedback")
            fb_text = SubElement(feedback_container, "text")
            fb_text.text = normalize(opt.solution, macro_map)


def exercises_to_quiz_xml(
    exercises: Sequence[ParsedExercise],
    *,
    source_dirs: Sequence[Path] | None = None,
    macro_map: dict[str, MacroRule] | None = None,
) -> str:
    """Convert multiple exercises to a complete Moodle XML quiz string.

    Parameters
    ----------
    exercises:
        Sequence of parsed exercises to include.
    source_dirs:
        Parallel sequence of source directories for each exercise (for image
        resolution). If None or shorter than exercises, missing entries use None.
    macro_map:
        Custom macro expansion rules. Defaults to DEFAULT_MACRO_MAP.

    Returns
    -------
    str
        Complete ``<?xml ...?><quiz>...</quiz>`` string.
    """
    quiz = Element("quiz")

    for idx, exercise in enumerate(exercises):
        src_dir: Path | None = None
        if source_dirs is not None and idx < len(source_dirs):
            src_dir = source_dirs[idx]
        q_elem = exercise_to_xml(exercise, source_dir=src_dir, macro_map=macro_map)
        quiz.append(q_elem)

    body = tostring(quiz, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body
