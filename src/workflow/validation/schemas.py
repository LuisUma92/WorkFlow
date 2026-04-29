from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from workflow.db.models.academic import (
    DisciplineArea,
    _TAXONOMY_DOMAINS,
    _TAXONOMY_LEVELS,
)

__all__ = [
    "NoteFrontmatter",
    "ExerciseMetadata",
    "validate_note_frontmatter",
    "validate_exercise_metadata",
    "check_candidate_project_against_db",
    "CANDIDATE_PROJECT_RE",
]


CANDIDATE_PROJECT_RE = re.compile(r"^[0-9]{4}[A-Z]{2}-[0-9]{2}[A-Z]{2}$")
"""Format of an ADR ITEP-0009 forward reference: ``DDTTAA-YYPP``."""

_VALID_NOTE_TYPES = {"permanent", "literature", "fleeting"}
_VALID_EXERCISE_TYPES = {
    "multichoice",
    "shortanswer",
    "essay",
    "numerical",
    "truefalse",
}
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_VALID_TAXONOMY_LEVELS = set(_TAXONOMY_LEVELS)
_VALID_TAXONOMY_DOMAINS = set(_TAXONOMY_DOMAINS)


@dataclass(frozen=True)
class NoteFrontmatter:
    id: str
    title: str
    tags: tuple[str, ...] = ()
    created: str | None = None
    concepts: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    exercises: tuple[str, ...] = ()
    images: tuple[str, ...] = ()
    type: str = "permanent"
    candidate_project: str | None = None


@dataclass(frozen=True)
class ExerciseMetadata:
    id: str
    type: str
    difficulty: str
    taxonomy_level: str
    taxonomy_domain: str
    tags: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()


def _string_list(data: dict, key: str, errors: list[str]) -> list[str]:
    raw = data.get(key, [])
    if not isinstance(raw, list):
        errors.append(f"'{key}' must be a list")
        return []
    if not all(isinstance(x, str) for x in raw):
        errors.append(f"all items in '{key}' must be strings")
        return []
    return list(raw)


def _validate_candidate_project(data: dict, errors: list[str]) -> str | None:
    value = data.get("candidate_project", None)
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append("'candidate_project' must be a string DDTTAA-YYPP")
        return None
    if not CANDIDATE_PROJECT_RE.match(value):
        errors.append(
            "'candidate_project' must match DDTTAA-YYPP "
            f"(e.g. '0010MC-26ST'); got '{value}'"
        )
        return None
    return value


def validate_note_frontmatter(data: dict) -> tuple[NoteFrontmatter | None, list[str]]:
    """Parse and validate note frontmatter dict.

    Returns (NoteFrontmatter, []) on success or (None, [errors]) on failure.
    """
    errors: list[str] = []

    note_id = data.get("id")
    if not note_id or not isinstance(note_id, str):
        errors.append("'id' is required and must be a non-empty string")

    title = data.get("title")
    if not title or not isinstance(title, str):
        errors.append("'title' is required and must be a non-empty string")

    tags = _string_list(data, "tags", errors)
    concepts = _string_list(data, "concepts", errors)
    references = _string_list(data, "references", errors)
    exercises = _string_list(data, "exercises", errors)
    images = _string_list(data, "images", errors)

    created = data.get("created", None)
    if created is not None and not isinstance(created, str):
        errors.append("'created' must be a string (ISO date) or null")
        created = None

    note_type = data.get("type", "permanent")
    if note_type not in _VALID_NOTE_TYPES:
        errors.append(
            f"'type' must be one of {sorted(_VALID_NOTE_TYPES)}, got '{note_type}'"
        )

    candidate_project = _validate_candidate_project(data, errors)

    if errors:
        return None, errors

    return (
        NoteFrontmatter(
            id=note_id,
            title=title,
            tags=tuple(tags),
            created=created,
            concepts=tuple(concepts),
            references=tuple(references),
            exercises=tuple(exercises),
            images=tuple(images),
            type=note_type,
            candidate_project=candidate_project,
        ),
        [],
    )


def validate_exercise_metadata(data: dict) -> tuple[ExerciseMetadata | None, list[str]]:
    """Parse and validate exercise metadata dict.

    Returns (ExerciseMetadata, []) on success or (None, [errors]) on failure.
    """
    errors: list[str] = []

    ex_id = data.get("id")
    if not ex_id or not isinstance(ex_id, str):
        errors.append("'id' is required and must be a non-empty string")

    ex_type = data.get("type")
    if not ex_type or not isinstance(ex_type, str):
        errors.append("'type' is required and must be a non-empty string")
    elif ex_type not in _VALID_EXERCISE_TYPES:
        errors.append(
            f"'type' must be one of {sorted(_VALID_EXERCISE_TYPES)}, got '{ex_type}'"
        )

    difficulty = data.get("difficulty")
    if not difficulty or not isinstance(difficulty, str):
        errors.append("'difficulty' is required and must be a non-empty string")
    elif difficulty not in _VALID_DIFFICULTIES:
        errors.append(
            f"'difficulty' must be one of {sorted(_VALID_DIFFICULTIES)}, got '{difficulty}'"
        )

    taxonomy_level = data.get("taxonomy_level")
    if not taxonomy_level or not isinstance(taxonomy_level, str):
        errors.append("'taxonomy_level' is required and must be a non-empty string")
    elif taxonomy_level not in _VALID_TAXONOMY_LEVELS:
        errors.append(
            f"'taxonomy_level' must be one of {sorted(_VALID_TAXONOMY_LEVELS)}, got '{taxonomy_level}'"
        )

    taxonomy_domain = data.get("taxonomy_domain")
    if not taxonomy_domain or not isinstance(taxonomy_domain, str):
        errors.append("'taxonomy_domain' is required and must be a non-empty string")
    elif taxonomy_domain not in _VALID_TAXONOMY_DOMAINS:
        errors.append(
            f"'taxonomy_domain' must be one of {sorted(_VALID_TAXONOMY_DOMAINS)}, got '{taxonomy_domain}'"
        )

    tags = data.get("tags", [])
    if not isinstance(tags, list):
        errors.append("'tags' must be a list")
        tags = []
    elif not all(isinstance(t, str) for t in tags):
        errors.append("all items in 'tags' must be strings")
        tags = []

    concepts = data.get("concepts", [])
    if not isinstance(concepts, list):
        errors.append("'concepts' must be a list")
        concepts = []
    elif not all(isinstance(c, str) for c in concepts):
        errors.append("all items in 'concepts' must be strings")
        concepts = []

    if errors:
        return None, errors

    return (
        ExerciseMetadata(
            id=ex_id,
            type=ex_type,
            difficulty=difficulty,
            taxonomy_level=taxonomy_level,
            taxonomy_domain=taxonomy_domain,
            tags=tuple(tags),
            concepts=tuple(concepts),
        ),
        [],
    )


def check_candidate_project_against_db(
    candidate_project: str | None,
    session: Session,
) -> list[str]:
    """Return warnings (not errors) for an ADR ITEP-0009 forward reference.

    A ``candidate_project`` is well-formed (validated upstream) but its
    ``DDTTAA`` portion may name an area that has not been registered in the
    :class:`DisciplineArea` reference table. The forward-reference field is
    a *MAY* rule, so missing DDTTAA is reported as a warning, not an error.
    """
    if not candidate_project:
        return []
    if not CANDIDATE_PROJECT_RE.match(candidate_project):
        return []  # caller already raised an error
    area_code = candidate_project.split("-", 1)[0]
    exists = session.query(DisciplineArea).filter_by(code=area_code).first()
    if exists is None:
        return [
            f"candidate_project '{candidate_project}' references unknown "
            f"DisciplineArea {area_code!r}; run `workflow db import-codes "
            "--all` if the area should exist."
        ]
    return []
