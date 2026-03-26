from __future__ import annotations

from dataclasses import dataclass

from workflow.db.models.academic import _TAXONOMY_LEVELS, _TAXONOMY_DOMAINS

__all__ = [
    "NoteFrontmatter",
    "ExerciseMetadata",
    "validate_note_frontmatter",
    "validate_exercise_metadata",
]

_VALID_NOTE_TYPES = {"permanent", "literature", "fleeting"}
_VALID_EXERCISE_TYPES = {"multichoice", "shortanswer", "essay", "numerical", "truefalse"}
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
    type: str = "permanent"


@dataclass(frozen=True)
class ExerciseMetadata:
    id: str
    type: str
    difficulty: str
    taxonomy_level: str
    taxonomy_domain: str
    tags: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()


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

    tags = data.get("tags", [])
    if not isinstance(tags, list):
        errors.append("'tags' must be a list")
        tags = []
    elif not all(isinstance(t, str) for t in tags):
        errors.append("all items in 'tags' must be strings")
        tags = []

    created = data.get("created", None)
    if created is not None and not isinstance(created, str):
        errors.append("'created' must be a string (ISO date) or null")
        created = None

    concepts = data.get("concepts", [])
    if not isinstance(concepts, list):
        errors.append("'concepts' must be a list")
        concepts = []
    elif not all(isinstance(c, str) for c in concepts):
        errors.append("all items in 'concepts' must be strings")
        concepts = []

    references = data.get("references", [])
    if not isinstance(references, list):
        errors.append("'references' must be a list")
        references = []
    elif not all(isinstance(r, str) for r in references):
        errors.append("all items in 'references' must be strings")
        references = []

    note_type = data.get("type", "permanent")
    if note_type not in _VALID_NOTE_TYPES:
        errors.append(
            f"'type' must be one of {sorted(_VALID_NOTE_TYPES)}, got '{note_type}'"
        )

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
            type=note_type,
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
