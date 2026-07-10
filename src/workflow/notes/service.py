"""Pure service functions for note CRUD operations.

No Click, no DB access. All mutations re-validate via validate_note_frontmatter
before any disk write (lessons.md row 14, 17, 18).
"""

from __future__ import annotations

import dataclasses
import logging
import re
from collections import deque
from pathlib import Path

import yaml

from workflow.db.errors import AmbiguousLookupError, EntityNotFoundError
from workflow.notes.discovery import parse_frontmatter, walk_note_files
from workflow.notes.edges import RelationEntry, relations_to_flat_fm
from workflow.validation.schemas import (
    NoteFrontmatter,
    NoteRelations,
    RelationEdge,
    validate_note_frontmatter,
)

__all__ = [
    "NoteNotFound",
    "AmbiguousNoteId",
    "NoteValidationError",
    "create_note",
    "list_notes",
    "walk_connections",
    "read_note",
    "update_tags",
    "add_link",
    "add_relation_link",
    "resolve_workspace_root",
]

_log = logging.getLogger(__name__)

# Allowlist regex for note IDs (lessons.md row 14).  Defined once here; cli.py imports it.
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
# Regex for [[wikilinks]] in body text
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class NoteNotFound(EntityNotFoundError):
    """Raised when a note with the given id cannot be found."""


class AmbiguousNoteId(AmbiguousLookupError):
    """Raised when multiple notes share the same id in the search root."""


class NoteValidationError(Exception):
    """Raised when frontmatter fails validation before a write."""


def _validate_id(note_id: str) -> None:
    """Reject ids with path traversal characters (lessons.md rows 14, 18)."""
    if not _SAFE_ID_RE.match(note_id):
        raise ValueError(
            f"note_id {note_id!r} contains invalid characters. "
            "Use only letters, digits, dots, underscores, hyphens."
        )


def _assert_within(child: Path, root: Path) -> None:
    """Raise ValueError if *child* is not contained within *root* (H1).

    Uses Path.relative_to which is prefix-path-aware, not a string prefix check.
    """
    try:
        child.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"Path {child} escapes target directory {root}")


def _relation_edge_to_entry(edge_class: str, e: RelationEdge) -> RelationEntry:
    """Adapt a validated RelationEdge (id, type) to a RelationEntry.

    weight/rationale are dropped from frontmatter (decision 2026-07-09); the
    adapter always emits the RelationEntry defaults (weight=1.0, rationale=None).
    """
    return RelationEntry(target_zettel_id=e.id, relation_type=e.type, edge_class=edge_class)


def _relations_to_flat_dict(rel: NoteRelations) -> dict[str, list[str]]:
    """Serialize a NoteRelations DTO to the flat frontmatter schema.

    Reuses ``workflow.notes.edges.relations_to_flat_fm`` so the key strings
    are always derived from ``FRONTMATTER_RELATION_KEYS`` — never hard-coded
    here (ADR ITEP-0013 MUST rule).
    """
    entries = [
        _relation_edge_to_entry("structural", e) for e in rel.derived_from
    ] + [
        _relation_edge_to_entry("associative", e) for e in rel.links
    ]
    return relations_to_flat_fm(entries)


def _fm_to_yaml(fm: NoteFrontmatter) -> str:
    """Serialize NoteFrontmatter to YAML block preserving field order."""
    d: dict = {
        "id": fm.id,
        "title": fm.title,
        "aliases": list(fm.aliases),
        "type": fm.type,
        "tags": list(fm.tags),
        "concepts": list(fm.concepts),
        "references": list(fm.references),
        "exercises": list(fm.exercises),
        "images": list(fm.images),
    }
    if fm.created is not None:
        d["created"] = fm.created
    if fm.candidate_project is not None:
        d["candidate_project"] = fm.candidate_project
    if fm.main_topic is not None:
        d["main_topic"] = fm.main_topic
    if fm.discipline_area is not None:
        d["discipline_area"] = fm.discipline_area
    if fm.relations is not None:
        d.update(_relations_to_flat_dict(fm.relations))
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)


def _write_note_file(path: Path, fm: NoteFrontmatter, body: str) -> None:
    """Write frontmatter + body to path atomically (validate first).

    ``body`` is written byte-exact — no extra newline is added after the closing
    fence (H3: body_raw already carries its leading character, e.g. ``\n``).
    """
    # Re-validate before write
    fm_dict: dict = {
        "id": fm.id,
        "title": fm.title,
        "aliases": list(fm.aliases),
        "type": fm.type,
        "tags": list(fm.tags),
        "concepts": list(fm.concepts),
        "references": list(fm.references),
        "exercises": list(fm.exercises),
        "images": list(fm.images),
        "created": fm.created,
        "candidate_project": fm.candidate_project,
        "main_topic": fm.main_topic,
        "discipline_area": fm.discipline_area,
    }
    if fm.relations is not None:
        fm_dict.update(_relations_to_flat_dict(fm.relations))
    result, errors = validate_note_frontmatter(fm_dict)
    if errors:
        raise NoteValidationError(
            f"Frontmatter validation failed before write: {'; '.join(errors)}"
        )

    # Validate path containment with path-aware check (H1)
    _assert_within(path, path.parent)

    # H3: body is everything after the closing fence's \n (returned by parse_frontmatter).
    # Re-add "---\n" so the round-trip is byte-exact: "---\n<yaml>---\n<body>".
    content = "---\n" + _fm_to_yaml(fm) + "---\n" + body
    path.write_text(content, encoding="utf-8")


def create_note(target_dir: Path, fm: NoteFrontmatter, *, force: bool) -> Path:
    """Create a new note file at ``target_dir/<fm.id>.md``.

    Raises ``FileExistsError`` if file exists and ``force=False``.
    Raises ``ValueError`` if ``target_dir`` is a symlink (H1).
    Re-validates frontmatter before write.
    """
    _validate_id(fm.id)

    # H1: reject symlinked target_dir before any fs operation
    if target_dir.is_symlink():
        raise ValueError(
            f"target_dir {target_dir} is a symlink; supply the real directory path."
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{fm.id}.md"

    # H1: path-aware containment check
    _assert_within(path, target_dir)

    if path.exists() and not force:
        raise FileExistsError(f"Note {fm.id!r} already exists at {path}")

    body = ""  # empty body; _write_note_file adds the "---\n" separator
    _write_note_file(path, fm, body)
    return path


def list_notes(
    root: Path,
    *,
    tag: str | None = None,
    concept: str | None = None,
    candidate_project: str | None = None,
    note_type: str | None = None,
) -> list[tuple[Path, NoteFrontmatter]]:
    """Return all notes under ``root`` recursively, optionally filtered.

    Silently skips files whose frontmatter fails to parse (logs warning).
    """
    results: list[tuple[Path, NoteFrontmatter]] = []
    for path in walk_note_files(root):
        try:
            fm_dict, _ = parse_frontmatter(path)
        except (ValueError, yaml.YAMLError) as exc:
            _log.warning("Skipping %s: %s", path.name, exc)
            continue

        fm_obj, errors = validate_note_frontmatter(fm_dict)
        if errors or fm_obj is None:
            _log.warning("Skipping %s: validation errors: %s", path.name, errors)
            continue

        # Apply filters
        if tag is not None and tag not in fm_obj.tags:
            continue
        if concept is not None and concept not in fm_obj.concepts:
            continue
        if (
            candidate_project is not None
            and fm_obj.candidate_project != candidate_project
        ):
            continue
        if note_type is not None and fm_obj.type != note_type:
            continue

        results.append((path, fm_obj))

    return results


def _iter_scan_paths(root: Path) -> list[Path]:
    """Return all .md paths to scan for id-index building (recursive)."""
    return list(walk_note_files(root))


def _build_id_index(
    root: Path, *, skip_invalid: bool = True
) -> dict[str, list[tuple[Path, NoteFrontmatter | None, str, dict]]]:
    """Build id → [(path, fm_or_None, body, raw_dict)] index.

    Scans top-level files AND known type subdirs (permanent/literature/fleeting)
    for cross-directory ambiguity detection (H5).

    When ``skip_invalid=True`` (default for walk_connections / list_notes),
    entries that fail validation are omitted.
    When ``skip_invalid=False`` (for read_note), all parseable files are included.
    """
    index: dict[str, list[tuple[Path, NoteFrontmatter | None, str, dict]]] = {}
    for path in _iter_scan_paths(root):
        try:
            fm_dict, body = parse_frontmatter(path)
        except (ValueError, yaml.YAMLError):
            continue
        fm_obj, errors = validate_note_frontmatter(fm_dict)
        if skip_invalid and (errors or fm_obj is None):
            continue
        note_id = fm_dict.get("id")
        if not note_id or not isinstance(note_id, str):
            continue
        index.setdefault(note_id, []).append((path, fm_obj, body, fm_dict))
    return index


def read_note(root: Path, note_id: str) -> tuple[Path, NoteFrontmatter, str]:
    """Find and return (path, fm, body) for the note with ``note_id``.

    Raises ``NoteNotFound`` if absent, ``AmbiguousNoteId`` if duplicate ids.
    """
    _validate_id(note_id)
    index = _build_id_index(root, skip_invalid=True)
    matches = index.get(note_id, [])
    if len(matches) == 0:
        raise NoteNotFound(f"No note with id {note_id!r} found in {root}")
    if len(matches) > 1:
        raise AmbiguousNoteId(
            f"Multiple notes with id {note_id!r} found in {root}; "
            "rename duplicates before proceeding."
        )
    path, fm, body, _ = matches[0]
    assert fm is not None  # skip_invalid=True guarantees this
    return path, fm, body


def _raw_read_note(
    root: Path, note_id: str
) -> tuple[Path, NoteFrontmatter | None, str, dict]:
    """Like read_note but loads even files with invalid frontmatter."""
    _validate_id(note_id)
    index = _build_id_index(root, skip_invalid=False)
    matches = index.get(note_id, [])
    if len(matches) == 0:
        raise NoteNotFound(f"No note with id {note_id!r} found in {root}")
    if len(matches) > 1:
        raise AmbiguousNoteId(
            f"Multiple notes with id {note_id!r} found in {root}; "
            "rename duplicates before proceeding."
        )
    return matches[0]


def _collect_neighbours(
    fm: NoteFrontmatter, body: str, edge_types: set[str]
) -> list[str]:
    """Return outgoing neighbour ids for the given edge types.

    H2: Only ``wikilinks`` resolves to note ids via BFS.
    ``concepts``, ``references``, ``exercises`` are slugs/keys — a resolver
    does not exist yet (Phase B / ITEP-0012).  Requesting them emits a warning.
    """
    # Warn on unresolvable edge types (H2)
    unresolvable = edge_types & {"concepts", "references", "exercises"}
    if unresolvable:
        _log.warning(
            "Edge types %s are slug keys, not note ids — no resolver exists yet "
            "(deferred to Phase B / ITEP-0012). They will not be followed in BFS.",
            sorted(unresolvable),
        )

    neighbours: list[str] = []
    if "wikilinks" in edge_types:
        neighbours.extend(_WIKILINK_RE.findall(body))
    return neighbours


def walk_connections(
    root: Path,
    start_id: str,
    *,
    depth: int | None,
    edge_types: set[str],
) -> list[tuple[Path, NoteFrontmatter]]:
    """BFS walk from ``start_id`` following outgoing edges.

    H2: Only ``wikilinks`` edges resolve to note ids.  Other edge types emit a
    warning.  Default ``edge_types`` should be ``{'wikilinks'}``.

    Cycle-safe via visited set. ``depth=None`` means unlimited.
    Raises ``NoteNotFound`` if ``start_id`` is not found.
    """
    _validate_id(start_id)
    index = _build_id_index(root)

    if start_id not in index:
        raise NoteNotFound(f"No note with id {start_id!r} found in {root}")

    results: list[tuple[Path, NoteFrontmatter]] = []
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_id, 0)])

    while queue:
        current_id, current_depth = queue.popleft()
        if current_id in visited or current_id not in index:
            continue
        visited.add(current_id)

        path, fm, body, _ = index[current_id][0]
        if fm is None:
            continue
        results.append((path, fm))

        if depth is not None and current_depth >= depth:
            continue

        for neighbour_id in _collect_neighbours(fm, body, edge_types):
            if neighbour_id not in visited:
                queue.append((neighbour_id, current_depth + 1))

    return results


def update_tags(
    root: Path,
    note_id: str,
    *,
    add: tuple[str, ...],
    remove: tuple[str, ...],
) -> tuple[Path, NoteFrontmatter]:
    """Add and/or remove tags on the note with ``note_id``.

    H4: Returns ``(path, updated_fm)`` — caller must NOT re-read the file.
    Idempotent. Re-validates before write.
    Raises ``NoteValidationError`` if on-disk frontmatter is already invalid.
    """
    path, fm, body, raw_dict = _raw_read_note(root, note_id)

    if fm is None:
        _, errors = validate_note_frontmatter(raw_dict)
        raise NoteValidationError(
            f"Frontmatter of {note_id!r} is already invalid: {'; '.join(errors)}"
        )

    current_tags = list(fm.tags)
    for t in remove:
        if t in current_tags:
            current_tags.remove(t)
    for t in add:
        if t not in current_tags:
            current_tags.append(t)

    new_fm = dataclasses.replace(fm, tags=tuple(current_tags))
    _write_note_file(path, new_fm, body)
    return path, new_fm


def _apply_link_to_frontmatter(
    fm: NoteFrontmatter,
    *,
    concept: str | None,
    reference: str | None,
    exercise: str | None,
    main_topic: str | None,
    remove: bool,
) -> NoteFrontmatter:
    """Return updated NoteFrontmatter after adding/removing one link target."""
    if concept is not None:
        if remove:
            new_concepts = tuple(c for c in fm.concepts if c != concept)
        else:
            new_concepts = (
                tuple(list(fm.concepts) + [concept])
                if concept not in fm.concepts
                else fm.concepts
            )
        return dataclasses.replace(fm, concepts=new_concepts)
    if reference is not None:
        if remove:
            new_refs = tuple(r for r in fm.references if r != reference)
        else:
            new_refs = (
                tuple(list(fm.references) + [reference])
                if reference not in fm.references
                else fm.references
            )
        return dataclasses.replace(fm, references=new_refs)
    if main_topic is not None:
        return dataclasses.replace(fm, main_topic=None if remove else main_topic)
    # exercise
    if remove:
        new_exs = tuple(e for e in fm.exercises if e != exercise)
    else:
        new_exs = (
            tuple(list(fm.exercises) + [exercise])
            if exercise not in fm.exercises
            else fm.exercises
        )
    return dataclasses.replace(fm, exercises=new_exs)


def _apply_link_to_db(
    session,
    *,
    note_row,
    concept_row,
    mt_row,
    concept: str | None,
    main_topic: str | None,
    remove: bool,
) -> None:
    """Persist concept-link or main_topic FK changes to session (no commit)."""
    if session is None or note_row is None:
        return
    if concept is not None:
        from workflow.notes.linker_ops import delete_note_concept, upsert_note_concept

        if remove:
            if concept_row is not None:
                delete_note_concept(session, note_id=note_row.id, concept_id=concept_row.id)
        else:
            if concept_row is not None:
                upsert_note_concept(session, note_id=note_row.id, concept_id=concept_row.id)
    if main_topic is not None:
        if remove:
            note_row.main_topic_id = None
        elif mt_row is not None:
            note_row.main_topic_id = mt_row.id


def _resolve_main_topic_link(
    fm: NoteFrontmatter,
    note_id: str,
    main_topic: str,
    session,
    *,
    strict: bool,
    remove: bool,
    issues: list[dict],
) -> tuple:
    """Resolve main_topic slug against DB; return (note_row, mt_row, issues, early_return).

    ``early_return=True`` means caller should return early without writing.
    """
    from sqlalchemy import select as sa_select

    from workflow.db.models.notes import Note as NoteModel
    from workflow.validation.schemas import check_main_topic_against_db

    note_row = session.scalars(
        sa_select(NoteModel).where(NoteModel.zettel_id == fm.id)
    ).first()
    if note_row is None:
        raise NoteNotFound(
            f"Note {note_id!r} is on disk but not in the DB. "
            "Run `workflow notes sync` first."
        )

    mt_row, mt_msgs = check_main_topic_against_db(main_topic, session)

    if mt_msgs:
        severity = "error" if strict else "warning"
        issues = issues + [{"severity": severity, "message": m} for m in mt_msgs]

    if strict and mt_row is None:
        raise NoteValidationError("; ".join(mt_msgs))

    early_return = not remove and mt_row is None
    return note_row, mt_row, issues, early_return


def add_link(
    root: Path,
    note_id: str,
    *,
    concept: str | None = None,
    reference: str | None = None,
    exercise: str | None = None,
    main_topic: str | None = None,
    session=None,
    strict: bool = False,
    remove: bool = False,
) -> tuple[Path, NoteFrontmatter, list[dict]]:
    """Append (or remove) an entry from ``concepts``/``references``/``exercises``/``main_topic`` (idempotent).

    Returns ``(path, updated_fm, issues)`` where ``issues`` is a list of
    ``{"severity": ..., "message": ...}`` dicts from resolution (may be empty).

    When ``concept`` is given and ``session`` is not None:
    - Resolves the Concept via ``resolve_concepts()``.
    - On strict + error-severity issue → raises ``NoteValidationError`` before any write.
    - On lenient + concept not found → returns without modifying frontmatter or DB.
    - On found → upserts a ``NoteConcept(note_id, concept_id)`` row.

    When ``main_topic`` is given and ``session`` is not None:
    - Resolves the MainTopic via ``check_main_topic_against_db()``.
    - On strict + miss → raises ``NoteValidationError`` before any write.
    - On lenient + miss → returns without modifying frontmatter or DB.
    - On found → sets ``Note.main_topic_id`` FK.

    When ``remove=True``:
    - Drops the target from the frontmatter tuple (idempotent).
    - If ``concept`` + session given: deletes the matching ``NoteConcept`` row.
    - If ``main_topic`` + session given: clears ``Note.main_topic_id`` FK.

    Raises ``NoteNotFound`` if note file is absent.
    Raises ``NoteValidationError`` if on-disk frontmatter is already invalid, or on strict miss.
    Raises ``NoteNotFound`` (DB) if note not in DB but session provided (user must sync first).
    """
    from sqlalchemy import select as sa_select

    path, fm, body, raw_dict = _raw_read_note(root, note_id)
    if fm is None:
        _, errors = validate_note_frontmatter(raw_dict)
        raise NoteValidationError(
            f"Frontmatter of {note_id!r} is already invalid: {'; '.join(errors)}"
        )

    issues: list[dict] = []

    # ── resolve DB objects when session is provided ─────────────────────────
    note_row = None
    concept_row = None
    mt_row = None

    if session is not None and concept is not None:
        from workflow.concept.service import resolve_concepts
        from workflow.db.models.notes import Note as NoteModel

        note_row = session.scalars(
            sa_select(NoteModel).where(NoteModel.zettel_id == fm.id)
        ).first()
        if note_row is None:
            raise NoteNotFound(
                f"Note {note_id!r} is on disk but not in the DB. "
                "Run `workflow notes sync` first."
            )

        found, issues = resolve_concepts([concept], session, strict=strict)

        if strict and any(i["severity"] == "error" for i in issues):
            raise NoteValidationError(
                "; ".join(i["message"] for i in issues if i["severity"] == "error")
            )

        if not remove and not found:
            # Lenient miss — skip frontmatter write, return early with warnings
            return path, fm, issues

        if found:
            concept_row = found[0]

    if session is not None and main_topic is not None:
        note_row, mt_row, issues, early_return = _resolve_main_topic_link(
            fm, note_id, main_topic, session, strict=strict, remove=remove, issues=issues
        )
        if early_return:
            return path, fm, issues

    new_fm = _apply_link_to_frontmatter(
        fm, concept=concept, reference=reference,
        exercise=exercise, main_topic=main_topic, remove=remove,
    )
    _apply_link_to_db(
        session, note_row=note_row, concept_row=concept_row,
        mt_row=mt_row, concept=concept, main_topic=main_topic, remove=remove,
    )
    _write_note_file(path, new_fm, body)
    return path, new_fm, issues


def _update_relation_bucket(
    bucket: list[RelationEdge],
    target_id: str,
    rel_type: str,
    *,
    remove: bool,
) -> None:
    """Mutate *bucket* in-place: add or remove the (target_id, rel_type) edge."""
    def _matches(e: RelationEdge) -> bool:
        return e.id == target_id and e.type == rel_type

    if remove:
        bucket[:] = [e for e in bucket if not _matches(e)]
    elif not any(_matches(e) for e in bucket):
        bucket.append(RelationEdge(id=target_id, type=rel_type))


def add_relation_link(
    root: Path,
    note_id: str,
    *,
    relation_type: str,
    target_zettel_id: str,
    remove: bool = False,
) -> tuple[Path, NoteFrontmatter, list[dict]]:
    """Append (or remove) a relation entry in the note's frontmatter ``relations`` block.

    The edge_class is derived from ``relation_type`` via ``edge_class_for_relation_type``.
    Operation is idempotent: re-adding the same (relation_type, target_zettel_id) is a
    no-op. Re-validates frontmatter via ``validate_note_frontmatter`` before any write.

    Returns ``(path, updated_fm, issues)`` where issues is always ``[]`` (kept for
    API symmetry with ``add_link``).

    Raises:
        ValueError: if ``relation_type`` is unknown or ``target_zettel_id`` is malformed.
        NoteNotFound: if the note file is not found.
        NoteValidationError: if existing frontmatter is already invalid.
    """
    from workflow.db.models.notes import (
        ZETTEL_ID_RE as _ZETTEL_ID_RE,
        edge_class_for_relation_type,
    )

    # Validate relation_type
    edge_class = edge_class_for_relation_type(relation_type)
    if edge_class is None:
        from workflow.db.models.notes import (
            _STRUCTURAL_RELATION_TYPES_ORDERED,
            _ASSOCIATIVE_RELATION_TYPES_ORDERED,
        )
        valid = list(_STRUCTURAL_RELATION_TYPES_ORDERED) + list(_ASSOCIATIVE_RELATION_TYPES_ORDERED)
        raise ValueError(
            f"Unknown relation type {relation_type!r}. Valid types: {valid}"
        )

    # Validate target zettel_id
    if not _ZETTEL_ID_RE.match(target_zettel_id):
        raise ValueError(
            f"target_zettel_id {target_zettel_id!r} must match NanoID format "
            "^[A-Za-z0-9_-]{8,21}$"
        )

    path, fm, body, raw_dict = _raw_read_note(root, note_id)
    if fm is None:
        _, errors = validate_note_frontmatter(raw_dict)
        raise NoteValidationError(
            f"Frontmatter of {note_id!r} is already invalid: {'; '.join(errors)}"
        )

    # Build updated relations
    current = fm.relations if fm.relations is not None else NoteRelations()
    derived, links = list(current.derived_from), list(current.links)

    target_bucket = derived if edge_class == "structural" else links
    _update_relation_bucket(target_bucket, target_zettel_id, relation_type, remove=remove)

    new_relations: NoteRelations | None = (
        NoteRelations(derived_from=tuple(derived), links=tuple(links))
        if (derived or links) else None
    )

    new_fm = dataclasses.replace(fm, relations=new_relations)
    _write_note_file(path, new_fm, body)
    return path, new_fm, []


def resolve_workspace_root(start: Path) -> Path:
    """Walk up from ``start`` looking for config.yaml or .git.

    Falls back to ``start`` (CWD) with a log warning if neither is found.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "config.yaml").exists() or (candidate / ".git").exists():
            return candidate
    _log.warning(
        "No config.yaml or .git found above %s; using CWD as workspace root.", start
    )
    return start
