"""Exercise placeholder file generator.

Generates .tex exercise files with commented YAML metadata headers,
ready to be filled in and synced to the database via ``exercise sync``.

See ADR-0010 for file-as-truth persistence design.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["GeneratedExercise", "generate_exercise_file", "generate_from_content"]

_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_safe_id(value: str, field_name: str) -> None:
    """Validate that a string is safe to use in filenames."""
    if not _SAFE_ID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} contains unsafe characters: {value!r}. "
            f"Only alphanumeric, hyphens, underscores, and dots are allowed."
        )


@dataclass(frozen=True)
class GeneratedExercise:
    """Result of generating an exercise placeholder file."""

    exercise_id: str
    file_path: Path
    created: bool  # False if file already existed (skipped)


def _build_tags_yaml(tags: list[str] | None) -> str:
    """Render tags list as inline YAML sequence."""
    if tags is None:
        return "[]"
    items = ", ".join(tags)
    return f"[{items}]"


def _render_template(
    exercise_id: str,
    *,
    exercise_type: str,
    difficulty: str,
    taxonomy_level: str,
    taxonomy_domain: str,
    tags: list[str] | None,
    book_cite: str | None,
    chapter: int | None,
    exercise_num: int | None,
) -> str:
    """Render the .tex content for an exercise placeholder."""
    tags_str = _build_tags_yaml(tags)

    # Build the \ifthenelse body
    if chapter is not None and exercise_num is not None:
        cite_comment = f" % \\cite{{{book_cite}}}" if book_cite else ""
        exa_line = f"  \\exa[{chapter}]{{{exercise_num}}}{cite_comment}"
    else:
        exa_line = "  % (no book reference)"

    lines = [
        "% ---",
        f"% id: {exercise_id}",
        f"% type: {exercise_type}",
        f"% difficulty: {difficulty}",
        f"% taxonomy_level: {taxonomy_level}",
        f"% taxonomy_domain: {taxonomy_domain}",
        f"% tags: {tags_str}",
        "% status: placeholder",
        "% ---",
        r"\ifthenelse{\boolean{main}}{",
        exa_line,
        "}{",
        "}",
        r"\question{",
        "  ...",
        "}{",
        "}",
        "",
    ]
    return "\n".join(lines)


def generate_exercise_file(
    output_dir: Path,
    exercise_id: str,
    *,
    exercise_type: str = "essay",
    difficulty: str = "medium",
    taxonomy_level: str = "Usar-Aplicar",
    taxonomy_domain: str = "Procedimiento Mental",
    tags: list[str] | None = None,
    book_cite: str | None = None,
    chapter: int | None = None,
    exercise_num: int | None = None,
) -> GeneratedExercise:
    """Generate a single exercise placeholder .tex file.

    Creates a file at output_dir/{exercise_id}.tex with:
    - Commented YAML metadata block
    - \\ifthenelse main guard with \\exa[ch]{num} if chapter+exercise_num provided
    - \\question{...}{} skeleton
    - status: placeholder

    If file already exists, returns created=False without overwriting.
    """
    _validate_safe_id(exercise_id, "exercise_id")
    file_path = output_dir / f"{exercise_id}.tex"

    if file_path.exists():
        return GeneratedExercise(
            exercise_id=exercise_id, file_path=file_path, created=False
        )

    content = _render_template(
        exercise_id,
        exercise_type=exercise_type,
        difficulty=difficulty,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
        tags=tags,
        book_cite=book_cite,
        chapter=chapter,
        exercise_num=exercise_num,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return GeneratedExercise(exercise_id=exercise_id, file_path=file_path, created=True)


def generate_from_content(
    output_dir: Path,
    book_cite: str,
    chapter: int,
    first_exercise: int,
    last_exercise: int,
    *,
    tags: list[str] | None = None,
    exercise_type: str = "essay",
    difficulty: str = "medium",
    taxonomy_level: str = "Usar-Aplicar",
    taxonomy_domain: str = "Procedimiento Mental",
) -> list[GeneratedExercise]:
    """Generate exercise files for a range of exercises from a book chapter.

    Creates files named {book_cite}-ch{chapter:02d}-{num:03d}.tex
    for each exercise in [first_exercise, last_exercise] (inclusive).
    """
    _validate_safe_id(book_cite, "book_cite")
    results: list[GeneratedExercise] = []

    for num in range(first_exercise, last_exercise + 1):
        exercise_id = f"{book_cite}-ch{chapter:02d}-{num:03d}"
        result = generate_exercise_file(
            output_dir,
            exercise_id,
            exercise_type=exercise_type,
            difficulty=difficulty,
            taxonomy_level=taxonomy_level,
            taxonomy_domain=taxonomy_domain,
            tags=tags,
            book_cite=book_cite,
            chapter=chapter,
            exercise_num=num,
        )
        results.append(result)

    return results
