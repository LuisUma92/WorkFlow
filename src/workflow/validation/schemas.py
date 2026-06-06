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
    "RelationEdge",
    "NoteRelations",
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

# ITEP-0013 edge type vocabularies.
_STRUCTURAL_REL_TYPES: frozenset[str] = frozenset(
    {"continuation", "refines", "branches", "synthesis", "rebuttal"}
)
_ASSOCIATIVE_REL_TYPES: frozenset[str] = frozenset(
    {"supports", "contradicts", "expands", "see_also"}
)
_VALID_LITERATURE_ORIGINS = {"prisma", "manual"}
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
class RelationEdge:
    """One edge item from ITEP-0013 ``relations.derived_from`` or ``relations.links``."""

    id: str
    type: str
    weight: float | None = None
    note: str | None = None


@dataclass(frozen=True)
class NoteRelations:
    """Parsed ``relations:`` block from note frontmatter (ITEP-0013)."""

    derived_from: tuple[RelationEdge, ...] = ()
    links: tuple[RelationEdge, ...] = ()


@dataclass(frozen=True)
class NoteFrontmatter:
    id: str
    title: str
    aliases: tuple[str, ...] = ()
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
    # Wave C C1 — PRISMA-provenance keys (literature notes only, all optional).
    bibkey: str | None = None
    prisma_review_record_id: int | None = None
    prisma_keyword_id: int | None = None
    origin: str | None = None
    # ITEP-0013 — note relation graph (DTO only; no DB persistence in this slice).
    entry_point: bool = False
    relations: NoteRelations | None = None


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


def _validate_literature_provenance(
    data: dict, errors: list[str]
) -> tuple[str | None, int | None, int | None, str | None]:
    """Validate PRISMA-provenance keys for literature notes.

    All four keys are optional.  Returns (bibkey, prisma_review_record_id,
    prisma_keyword_id, origin).
    """
    bibkey = data.get("bibkey", None)
    if bibkey is not None and not isinstance(bibkey, str):
        errors.append("'bibkey' must be a string or absent")
        bibkey = None

    prr_id = data.get("prisma_review_record_id", None)
    if prr_id is not None and (isinstance(prr_id, bool) or not isinstance(prr_id, int)):
        errors.append("'prisma_review_record_id' must be an integer or null")
        prr_id = None

    pk_id = data.get("prisma_keyword_id", None)
    if pk_id is not None and (isinstance(pk_id, bool) or not isinstance(pk_id, int)):
        errors.append("'prisma_keyword_id' must be an integer or null")
        pk_id = None

    origin = data.get("origin", None)
    if origin is not None and not isinstance(origin, str):
        errors.append("'origin' must be a string or absent")
        origin = None

    return bibkey, prr_id, pk_id, origin


def _validate_relation_edge(
    item: object,
    slot: str,
    allowed_types: frozenset[str],
    errors: list[str],
) -> RelationEdge | None:
    if not isinstance(item, dict):
        errors.append(f"each item in 'relations.{slot}' must be a mapping")
        return None
    edge_id = item.get("id")
    if not edge_id or not isinstance(edge_id, str):
        errors.append(f"'id' is required in each 'relations.{slot}' item")
        return None
    edge_type = item.get("type")
    if not edge_type or not isinstance(edge_type, str):
        errors.append(f"'type' is required in each 'relations.{slot}' item")
        return None
    if edge_type not in allowed_types:
        errors.append(
            f"'relations.{slot}' item has invalid type '{edge_type}'; "
            f"allowed: {sorted(allowed_types)}"
        )
        return None
    weight = item.get("weight")
    if weight is not None and (isinstance(weight, bool) or not isinstance(weight, (int, float))):
        errors.append(f"'weight' in 'relations.{slot}' must be a number")
        weight = None
    note = item.get("note")
    if note is not None and not isinstance(note, str):
        errors.append(f"'note' in 'relations.{slot}' must be a string")
        note = None
    return RelationEdge(id=edge_id, type=edge_type, weight=weight, note=note)


def _validate_relations(
    data: dict, errors: list[str]
) -> NoteRelations | None:
    raw = data.get("relations")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append("'relations' must be a mapping or absent")
        return None

    derived: list[RelationEdge] = []
    raw_derived = raw.get("derived_from", [])
    if not isinstance(raw_derived, list):
        errors.append("'relations.derived_from' must be a list")
    else:
        for item in raw_derived:
            edge = _validate_relation_edge(item, "derived_from", _STRUCTURAL_REL_TYPES, errors)
            if edge is not None:
                derived.append(edge)

    links: list[RelationEdge] = []
    raw_links = raw.get("links", [])
    if not isinstance(raw_links, list):
        errors.append("'relations.links' must be a list")
    else:
        for item in raw_links:
            edge = _validate_relation_edge(item, "links", _ASSOCIATIVE_REL_TYPES, errors)
            if edge is not None:
                links.append(edge)

    return NoteRelations(derived_from=tuple(derived), links=tuple(links))


def _validate_entry_point(data: dict, errors: list[str]) -> bool:
    val = data.get("entry_point", False)
    if not isinstance(val, bool):
        errors.append("'entry_point' must be a boolean (true/false)")
        return False
    return val


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

    aliases = _string_list(data, "aliases", errors)
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

    # PRISMA-provenance fields — validated for literature notes; silently
    # ignored (not an error) on permanent/fleeting notes.
    bibkey: str | None = None
    prisma_review_record_id: int | None = None
    prisma_keyword_id: int | None = None
    origin: str | None = None
    if note_type == "literature":
        bibkey, prisma_review_record_id, prisma_keyword_id, origin = (
            _validate_literature_provenance(data, errors)
        )

    entry_point = _validate_entry_point(data, errors)
    relations = _validate_relations(data, errors)

    if errors:
        return None, errors

    return (
        NoteFrontmatter(
            id=note_id,
            title=title,
            aliases=tuple(aliases),
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
            bibkey=bibkey,
            prisma_review_record_id=prisma_review_record_id,
            prisma_keyword_id=prisma_keyword_id,
            origin=origin,
            entry_point=entry_point,
            relations=relations,
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
      DisciplineArea (via ``concept.content.topic.discipline_area_id``) is compared
      against the note's MainTopic DisciplineArea (``note_mt.discipline_area_id``).
      A mismatch produces an issue at the same severity level as an unknown code.
      NOTE: The ``strict`` flag (originally named ``--strict-main-topic`` at the CLI)
      now gates a *discipline-area* check, not a main_topic check. The CLI flag name
      is preserved for backwards compatibility; its semantics changed post-Topic-reroot.
    - When ``fm.main_topic`` is None the discipline-area mismatch check is skipped.
    - Empty ``concepts`` list returns ``[]`` immediately (no DB hits).

    Mirrors ``check_main_topic_against_db`` strict-vs-lenient pattern (PB.2).
    """
    from workflow.concept.service import concept_discipline_area, resolve_concepts

    if not fm.concepts:
        return []

    found, issues = resolve_concepts(list(fm.concepts), session, strict=strict)

    # discipline-area mismatch: only when note has a resolvable main_topic
    if fm.main_topic is not None and found:
        note_mt, _ = check_main_topic_against_db(fm.main_topic, session)
        if note_mt is not None:
            note_da_id: int | None = note_mt.discipline_area_id
            for concept in found:
                concept_da = concept_discipline_area(concept)
                if concept_da is None:
                    issues.append(
                        {
                            "severity": "warning",
                            "message": (
                                f"concept {concept.code!r} has no resolved "
                                "discipline_area chain (content → topic → discipline_area)."
                            ),
                        }
                    )
                    continue
                if concept_da.id != note_da_id:
                    severity = "error" if strict else "warning"
                    issues.append(
                        {
                            "severity": severity,
                            "message": (
                                f"concept {concept.code!r} belongs to "
                                f"discipline_area {concept_da.code!r}"
                                f" but note's main_topic {note_mt.code!r} belongs to"
                                f" discipline_area_id={note_da_id}."
                            ),
                        }
                    )

    return issues
