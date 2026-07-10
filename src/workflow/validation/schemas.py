from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.academic import (
    _TAXONOMY_DOMAINS,
    _TAXONOMY_LEVELS,
)
from workflow.db.models.notes import (
    ASSOCIATIVE_KEY_PREFIX as _ASSOCIATIVE_KEY_PREFIX,
    FRONTMATTER_RELATION_KEYS as _FRONTMATTER_RELATION_KEYS,
    NoteEdge,
    Note,
    STRUCTURAL_KEY_PREFIX as _STRUCTURAL_KEY_PREFIX,
    ZETTEL_ID_RE as _ZETTEL_ID_RE,
)

__all__ = [
    "NoteFrontmatter",
    "RelationEdge",
    "NoteRelations",
    "ExerciseMetadata",
    "validate_note_frontmatter",
    "validate_note_frontmatter_with_warnings",
    "validate_exercise_metadata",
    "check_candidate_project_against_db",
    "check_main_topic_against_db",
    "check_discipline_area_consistency",
    "check_concepts_against_db",
    "check_graph_against_db",
    "CANDIDATE_PROJECT_RE",
]


CANDIDATE_PROJECT_RE = re.compile(r"^[0-9]{4}[A-Z]{2}-[0-9]{2}[A-Z]{2}$")
"""Format of an ADR ITEP-0009 forward reference: ``DDTTAA-YYPP``."""

_VALID_NOTE_TYPES = {"permanent", "literature", "fleeting"}

# ITEP-0013 edge-type vocabularies + zettel_id format are imported from the
# NoteEdge model (single source of truth) — see top-of-file imports.
_VALID_LITERATURE_ORIGINS = {"prisma", "manual"}


def _valid_exercise_types() -> frozenset[str]:
    """Single source of truth for exercise-type vocabulary.

    Deferred import: ``workflow.exercise.domain`` imports ``ExerciseMetadata``
    from this module, so importing ``ExerciseType`` at module level here
    would be circular. See ``workflow.db.models.exercises.Exercise.type``
    (the ORM column) — also keyed on ``ExerciseType.value``.
    """
    from workflow.exercise.domain import ExerciseType

    return frozenset(e.value for e in ExerciseType)


_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_VALID_TAXONOMY_LEVELS = set(_TAXONOMY_LEVELS)
_VALID_TAXONOMY_DOMAINS = set(_TAXONOMY_DOMAINS)

# Explicit exercise `status:` values accepted in commented-YAML frontmatter.
# Shared with workflow.exercise.parser so the enum has a single source of
# truth across the parse (file) and validate (schema) entry points.
_VALID_EXPLICIT_STATUSES = ("placeholder", "in_progress", "complete")

# Keys read by validate_exercise_metadata (including `status`, which is
# checked here but excluded from the returned ExerciseMetadata dataclass).
# Anything outside this set is a likely typo — warn with a difflib suggestion.
_RECOGNIZED_EXERCISE_KEYS = frozenset({
    "id",
    "type",
    "difficulty",
    "taxonomy_level",
    "taxonomy_domain",
    "tags",
    "concepts",
    "status",
})


@dataclass(frozen=True)
class RelationEdge:
    """One edge item parsed from a flat ``derived_from_*``/``links_*`` frontmatter key.

    ``weight``/``note`` are DELIBERATELY absent (decision 2026-07-09): Obsidian
    Properties cannot represent the nested ``relations:`` mapping, so the
    canonical frontmatter schema is 9 flat keys whose values are plain lists
    of zettel_id strings — there is no slot left for per-edge weight/rationale.
    """

    id: str
    type: str


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


def _check_legacy_relations(data: dict, warnings_out: list[str]) -> None:
    """Append a warning (never an error) on a legacy nested ``relations:`` block.

    Fires for a well-formed nested mapping AND for a corrupted ``relations:``
    string (the signature Obsidian Properties leaves behind after collapsing
    the nested mapping on save) — mirrors ``workflow.notes.edges.has_legacy_relations``.
    """
    raw = data.get("relations")
    if isinstance(raw, dict) and raw or isinstance(raw, str):
        warnings_out.append(
            "legacy nested relations: — run 'workflow notes migrate-relations'"
        )


def _check_unknown_relation_keys(data: dict, warnings_out: list[str]) -> None:
    """Append warnings for ``derived_from_*``/``links_*`` keys outside the vocabulary.

    Any other key shape is none of this validator's business (handled by the
    rest of ``validate_note_frontmatter``).
    """
    for key in data:
        if key in _FRONTMATTER_RELATION_KEYS:
            continue
        if not (
            key.startswith(f"{_STRUCTURAL_KEY_PREFIX}_")
            or key.startswith(f"{_ASSOCIATIVE_KEY_PREFIX}_")
        ):
            continue
        suggestion = difflib.get_close_matches(key, _FRONTMATTER_RELATION_KEYS, n=1)
        if suggestion:
            warnings_out.append(
                f"unknown frontmatter key '{key}' — did you mean '{suggestion[0]}'?"
            )
        else:
            warnings_out.append(f"unknown frontmatter key '{key}'")


def _validate_relations(
    data: dict, errors: list[str], warnings_out: list[str] | None = None
) -> NoteRelations | None:
    """Parse the 9 flat ``derived_from_*``/``links_*`` frontmatter keys.

    Never descends a nested ``relations:`` mapping — that shape is legacy
    (warning only, see ``_check_legacy_relations``); a note using it has no
    flat keys and therefore round-trips to ``NoteRelations()`` / ``None``.
    Key strings are always derived from ``FRONTMATTER_RELATION_KEYS`` — the
    ITEP-0013 vocabulary lives solely in ``workflow.db.models.notes``.

    ``warnings_out`` collects non-blocking warnings (legacy-nested block,
    unknown relation keys); ``None`` discards them (direct-helper callers).
    """
    sink = warnings_out if warnings_out is not None else []
    _check_legacy_relations(data, sink)
    _check_unknown_relation_keys(data, sink)

    derived: list[RelationEdge] = []
    links: list[RelationEdge] = []
    any_key_present = False

    for key, (edge_class, relation_type) in _FRONTMATTER_RELATION_KEYS.items():
        if key not in data:
            continue
        any_key_present = True
        raw = data[key]
        if isinstance(raw, dict):
            errors.append(
                f"{key}: must be a list of strings "
                "(mapping value looks like the legacy nested 'relations:' format)"
            )
            continue
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            errors.append(f"{key}: must be a list of strings")
            continue

        bucket = derived if edge_class == "structural" else links
        for item in raw:
            target_id = item.strip()
            if not target_id or not _ZETTEL_ID_RE.match(target_id):
                # Mirror the sync/ingest contract (workflow.notes.edges) — an id
                # that fails the NanoID format is silently dropped there, so
                # flag it here.
                errors.append(
                    f"'id' {target_id[:40]!r} in '{key}' must match "
                    "the NanoID format ^[A-Za-z0-9_-]{8,21}$"
                )
                continue
            bucket.append(RelationEdge(id=target_id, type=relation_type))

    if not any_key_present:
        return None
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
    """Parse and validate note frontmatter dict (thin delegator).

    Returns (NoteFrontmatter, []) on success or (None, [errors]) on failure.
    Drops the non-blocking warnings channel — signature and behavior are
    byte-identical for all existing ``fm, errors = ...`` callers. Callers that
    need warnings (e.g. ``workflow validate notes``) use
    ``validate_note_frontmatter_with_warnings``.
    """
    fm, errors, _warnings = validate_note_frontmatter_with_warnings(data)
    return fm, errors


def validate_note_frontmatter_with_warnings(
    data: dict,
) -> tuple[NoteFrontmatter | None, list[str], list[str]]:
    """Parse and validate note frontmatter, returning ``(fm, errors, warnings)``.

    Mirrors ``validate_exercise_metadata``'s three-tuple channel: ``warnings``
    are non-blocking (legacy nested ``relations:`` block; unknown
    ``derived_from_*``/``links_*`` keys with a difflib suggestion) and NEVER
    affect validity — ``fm`` is ``None`` iff ``errors`` is non-empty.
    """
    errors: list[str] = []
    warnings: list[str] = []

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
    relations = _validate_relations(data, errors, warnings)

    if errors:
        return None, errors, warnings

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
        warnings,
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


def _check_unknown_exercise_keys(data: dict) -> list[str]:
    """Warn on frontmatter keys outside the recognized set, with a difflib suggestion."""
    warnings: list[str] = []
    unknown_keys = set(data.keys()) - _RECOGNIZED_EXERCISE_KEYS
    for key in sorted(unknown_keys):
        suggestion = difflib.get_close_matches(key, _RECOGNIZED_EXERCISE_KEYS, n=1)
        if suggestion:
            warnings.append(
                f"unknown frontmatter key '{key}' — did you mean '{suggestion[0]}'?"
            )
        else:
            warnings.append(f"unknown frontmatter key '{key}'")
    return warnings


def _check_exercise_status(status: object) -> list[str]:
    """Validate an explicit `status:` value; absent (None) status is valid."""
    if status is None:
        return []
    if not isinstance(status, str) or status not in _VALID_EXPLICIT_STATUSES:
        return [f"'status' must be one of {list(_VALID_EXPLICIT_STATUSES)}, got '{status}'"]
    return []


def validate_exercise_metadata(
    data: dict,
) -> tuple[ExerciseMetadata | None, list[str], list[str]]:
    """Parse and validate exercise metadata dict.

    Returns ``(ExerciseMetadata, errors, warnings)``. The first element is
    ``None`` iff ``errors`` is non-empty. ``warnings`` never blocks validity
    (currently: unrecognized frontmatter keys, reported with a difflib
    closest-match suggestion).
    """
    errors: list[str] = []
    warnings: list[str] = _check_unknown_exercise_keys(data)

    ex_id = data.get("id")
    if not ex_id or not isinstance(ex_id, str):
        errors.append("'id' is required and must be a non-empty string")

    ex_type = data.get("type")
    if not ex_type or not isinstance(ex_type, str):
        errors.append("'type' is required and must be a non-empty string")
    elif ex_type not in _valid_exercise_types():
        errors.append(
            f"'type' must be one of {sorted(_valid_exercise_types())}, got '{ex_type}'"
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

    errors.extend(_check_exercise_status(data.get("status")))

    if errors:
        return None, errors, warnings

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
        warnings,
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


def check_graph_against_db(session: Session) -> list[dict[str, str]]:
    """Validate the NoteEdge graph against ITEP-0013 failure modes.

    Returns a list of issue dicts: ``{"severity": "error"|"warning", "message": str}``.

    Categories:
    - **Lineage cycles** (error): structural edges forming directed cycles.
      Detected via ``workflow.notes.dag.detect_structural_cycles``.
    - **Unresolved edges** (warning): NoteEdge rows with ``target_id IS NULL``.
    - **Orphan notes** (warning): Notes with zero outgoing AND zero incoming structural
      edges (true graph isolates). NOTE: ``entry_point: true`` is stored in frontmatter
      only, not in the DB; this check therefore reports all structural isolates,
      including entry-point notes that have no structural edges yet.
    - **Self-edges** (warning): NoteEdge where ``target_zettel_id`` matches the source
      note's own ``zettel_id``.  A DB CHECK prevents ``source_id == target_id``, but a
      self-reference by zettel_id with ``target_id IS NULL`` can slip through.
    - **Duplicate edges** (warning): same ``(source_id, target_zettel_id, relation_type)``
      appearing more than once.  Normally prevented by the UNIQUE constraint; reported
      defensively in case the constraint is ever bypassed.
    """
    from workflow.notes.dag import detect_structural_cycles

    issues: list[dict[str, str]] = []

    # --- 1. Lineage cycles (error) ---
    cycles = detect_structural_cycles(session)
    for cycle in cycles:
        issues.append({
            "severity": "error",
            "message": f"structural cycle detected (note ids): {cycle}",
        })

    # --- 2. Unresolved edges (warning) ---
    unresolved_rows = session.execute(
        select(NoteEdge.id, NoteEdge.source_id, NoteEdge.target_zettel_id).where(
            NoteEdge.target_id.is_(None)
        )
    ).all()
    for row in unresolved_rows:
        issues.append({
            "severity": "warning",
            "message": (
                f"unresolved edge (edge_id={row.id}, source_id={row.source_id}): "
                f"target_zettel_id={row.target_zettel_id!r} has no matching Note."
            ),
        })

    # --- 3. Orphan notes (warning) ---
    # True graph isolates: no outgoing AND no incoming structural edges.
    # NOTE: 'entry_point: true' is a frontmatter field not tracked in the DB,
    # so entry-point notes without any structural edges will appear here too.
    notes_with_outgoing = (
        select(NoteEdge.source_id)
        .where(NoteEdge.edge_class == "structural")
        .scalar_subquery()
    )
    notes_with_incoming = (
        select(NoteEdge.target_id)
        .where(
            NoteEdge.edge_class == "structural",
            NoteEdge.target_id.is_not(None),
        )
        .scalar_subquery()
    )
    orphan_rows = session.execute(
        select(Note.id, Note.zettel_id, Note.title).where(
            Note.id.not_in(notes_with_outgoing),
            Note.id.not_in(notes_with_incoming),
        )
    ).all()
    for row in orphan_rows:
        label = row.zettel_id or str(row.id)
        issues.append({
            "severity": "warning",
            "message": (
                f"orphan note (id={row.id}, zettel_id={label!r}): "
                "no structural edges in or out."
            ),
        })

    # --- 4. Self-edges (warning) ---
    SourceNote = aliased(Note)
    self_edge_rows = session.execute(
        select(NoteEdge.id, NoteEdge.source_id, NoteEdge.target_zettel_id)
        .join(SourceNote, NoteEdge.source_id == SourceNote.id)
        .where(
            NoteEdge.target_zettel_id == SourceNote.zettel_id,
            SourceNote.zettel_id.is_not(None),
        )
    ).all()
    for row in self_edge_rows:
        issues.append({
            "severity": "warning",
            "message": (
                f"self-edge (edge_id={row.id}, source_id={row.source_id}): "
                f"target_zettel_id={row.target_zettel_id!r} points back to the source note."
            ),
        })

    # --- 5. Duplicate edges (warning, defensive) ---
    # The UNIQUE(source_id, target_zettel_id, relation_type) constraint normally
    # prevents these; this check is defensive and reports any that slip through.
    dup_rows = session.execute(
        select(
            NoteEdge.source_id,
            NoteEdge.target_zettel_id,
            NoteEdge.relation_type,
            func.count(NoteEdge.id).label("cnt"),
        )
        .group_by(NoteEdge.source_id, NoteEdge.target_zettel_id, NoteEdge.relation_type)
        .having(func.count(NoteEdge.id) > 1)
    ).all()
    for row in dup_rows:
        issues.append({
            "severity": "warning",
            "message": (
                f"duplicate edge: source_id={row.source_id}, "
                f"target_zettel_id={row.target_zettel_id!r}, "
                f"relation_type={row.relation_type!r} appears {row.cnt} times."
            ),
        })

    return issues
