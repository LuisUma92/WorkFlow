from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.academic import (
    _TAXONOMY_DOMAINS,
    _TAXONOMY_LEVELS,
)

__all__ = [
    "NoteFrontmatter",
    "ExerciseMetadata",
    "validate_note_frontmatter",
    "validate_exercise_metadata",
    "check_candidate_project_against_db",
    "check_main_topic_against_db",
    "check_discipline_area_consistency",
    "check_concepts_against_db",
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
    # Phase B (ITEP-0009 Part II) — frontmatter linkage to MainTopic.
    # main_topic accepts either an int id or a code slug (e.g. "FI0006").
    main_topic: str | int | None = None
    discipline_area: str | None = None


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

    main_topic = _validate_main_topic(data, errors)
    discipline_area = _validate_discipline_area(data, errors)

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
            main_topic=main_topic,
            discipline_area=discipline_area,
        ),
        [],
    )


_DDTTAA_RE = re.compile(r"^[A-Z0-9]{6}$")


def _validate_main_topic(data: dict, errors: list[str]) -> str | int | None:
    value = data.get("main_topic")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        errors.append("'main_topic' must be a string slug or integer id")
        return None
    return value


def _validate_discipline_area(data: dict, errors: list[str]) -> str | None:
    value = data.get("discipline_area")
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append("'discipline_area' must be a string DDTTAA code")
        return None
    if not _DDTTAA_RE.match(value):
        errors.append(f"'discipline_area' must be a 6-char DDTTAA code; got '{value}'")
        return None
    return value


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


def check_main_topic_against_db(
    main_topic: str | int | None,
    session: Session,
    *,
    strict: bool = False,
) -> tuple[MainTopic | None, list[str]]:
    """Resolve ``main_topic`` against the global MainTopic table.

    Returns ``(MainTopic | None, messages)``. Messages are warnings under
    ``strict=False`` and errors under ``strict=True``; the prefix lets the
    caller route them to the appropriate channel.

    Resolution order: int id first, then ``MainTopic.code`` slug. An
    int-shaped string ("42") is tried as id first.
    """
    if main_topic is None:
        return None, []

    candidate_id: int | None = None
    candidate_slug: str | None = None
    if isinstance(main_topic, int):
        candidate_id = main_topic
    else:
        try:
            candidate_id = int(main_topic)
        except (TypeError, ValueError):
            candidate_slug = main_topic

    if candidate_id is not None:
        mt = session.query(MainTopic).filter_by(id=candidate_id).first()
        if mt is not None:
            return mt, []
        if candidate_slug is None and isinstance(main_topic, str):
            candidate_slug = main_topic

    if candidate_slug is not None:
        mt = session.query(MainTopic).filter_by(code=candidate_slug).first()
        if mt is not None:
            return mt, []

    msg = (
        f"main_topic {main_topic!r} does not resolve to any MainTopic "
        "(checked id then code)."
    )
    return None, [msg]


def check_discipline_area_consistency(
    main_topic_obj: MainTopic | None,
    discipline_area: str | None,
    session: Session,
) -> list[str]:
    """Return errors when frontmatter ``discipline_area`` disagrees with the
    resolved ``MainTopic.discipline_area_id``.

    No-op when either input is missing — the per-key validators handle
    presence/shape errors upstream.
    """
    if main_topic_obj is None or discipline_area is None:
        return []
    da = session.query(DisciplineArea).filter_by(code=discipline_area).first()
    if da is None:
        return [
            f"discipline_area {discipline_area!r} not found in "
            "DisciplineArea reference table."
        ]
    if da.id != main_topic_obj.discipline_area_id:
        return [
            f"frontmatter inconsistency: main_topic {main_topic_obj.code!r} "
            f"belongs to discipline_area_id={main_topic_obj.discipline_area_id} "
            f"but discipline_area={discipline_area!r} resolves to id={da.id}."
        ]
    return []


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


def check_concepts_against_db(
    fm: "NoteFrontmatter",
    session: Session,
    *,
    strict: bool = False,
) -> list[dict[str, str]]:
    """Validate frontmatter ``concepts`` codes against the global Concept table.

    Returns a list of issue dicts: ``{"severity": "warning"|"error", "message": str}``.

    Resolution:
    - Each code in ``fm.concepts`` is looked up by ``Concept.code``.
    - Unknown codes produce a warning (lenient) or error (strict).
    - When ``fm.main_topic`` resolves to a ``MainTopic``, each found concept's
      MainTopic (via ``concept.content.topic.main_topic``) is compared.
      A mismatch produces an issue at the same severity level as an unknown code.
    - When ``fm.main_topic`` is None the mt-mismatch check is skipped silently.
    - Empty ``concepts`` list returns ``[]`` immediately (no DB hits).

    Mirrors ``check_main_topic_against_db`` strict-vs-lenient pattern (PB.2).
    """
    from workflow.concept.service import concept_main_topic, resolve_concepts

    if not fm.concepts:
        return []

    found, issues = resolve_concepts(list(fm.concepts), session, strict=strict)

    # mt-mismatch: only when note has a resolvable main_topic
    if fm.main_topic is not None and found:
        note_mt, _ = check_main_topic_against_db(fm.main_topic, session)
        if note_mt is not None:
            for concept in found:
                concept_mt = concept_main_topic(concept)
                concept_mt_id = concept_mt.id if concept_mt is not None else None
                concept_mt_code = concept_mt.code if concept_mt is not None else "?"
                if concept_mt_id != note_mt.id:
                    severity = "error" if strict else "warning"
                    issues.append(
                        {
                            "severity": severity,
                            "message": (
                                f"concept {concept.code!r} belongs to "
                                f"main_topic {concept_mt_code!r}"
                                f" but note declares main_topic={note_mt.code!r}."
                            ),
                        }
                    )

    return issues
