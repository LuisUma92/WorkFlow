"""Pure service functions for note CRUD operations.

No Click, no DB access. All mutations re-validate via validate_note_frontmatter
before any disk write (lessons.md row 14, 17, 18).
"""

from __future__ import annotations

import dataclasses
import re
import sys
from collections import deque
from pathlib import Path

import yaml

from workflow.notes.discovery import iter_note_files, parse_frontmatter
from workflow.validation.schemas import NoteFrontmatter, validate_note_frontmatter

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
    "resolve_workspace_root",
]

# Allowlist regex for note IDs (lessons.md row 14)
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
# Regex for [[wikilinks]] in body text
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class NoteNotFound(Exception):
    """Raised when a note with the given id cannot be found."""


class AmbiguousNoteId(Exception):
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


def _fm_to_yaml(fm: NoteFrontmatter) -> str:
    """Serialize NoteFrontmatter to YAML block preserving field order."""
    d: dict = {
        "id": fm.id,
        "title": fm.title,
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
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)


def _write_note_file(path: Path, fm: NoteFrontmatter, body: str) -> None:
    """Write frontmatter + body to path atomically (validate first)."""
    # Re-validate before write
    fm_dict = {
        "id": fm.id,
        "title": fm.title,
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
    result, errors = validate_note_frontmatter(fm_dict)
    if errors:
        raise NoteValidationError(
            f"Frontmatter validation failed before write: {'; '.join(errors)}"
        )

    # Validate path containment (lessons.md row 18)
    resolved = path.resolve()
    root = path.parent.resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path {path} escapes target directory {root}")

    content = "---\n" + _fm_to_yaml(fm) + "---\n" + body
    path.write_text(content, encoding="utf-8")


def create_note(target_dir: Path, fm: NoteFrontmatter, *, force: bool) -> Path:
    """Create a new note file at ``target_dir/<fm.id>.md``.

    Raises ``FileExistsError`` if file exists and ``force=False``.
    Re-validates frontmatter before write.
    """
    _validate_id(fm.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{fm.id}.md"

    # Validate path containment (lessons.md row 18)
    resolved = path.resolve()
    if not str(resolved).startswith(str(target_dir.resolve())):
        raise ValueError(f"Computed path {path} escapes target_dir {target_dir}")

    if path.exists() and not force:
        raise FileExistsError(f"Note {fm.id!r} already exists at {path}")

    body = ""
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
    """Return top-level notes in ``root``, optionally filtered.

    Silently skips files whose frontmatter fails to parse (warn to stderr).
    """
    results: list[tuple[Path, NoteFrontmatter]] = []
    for path in iter_note_files(root):
        try:
            fm_dict, _ = parse_frontmatter(path)
        except (ValueError, yaml.YAMLError) as exc:
            print(f"[WARN] Skipping {path.name}: {exc}", file=sys.stderr)
            continue

        fm_obj, errors = validate_note_frontmatter(fm_dict)
        if errors or fm_obj is None:
            print(
                f"[WARN] Skipping {path.name}: validation errors: {errors}",
                file=sys.stderr,
            )
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


def _build_id_index(
    root: Path, *, skip_invalid: bool = True
) -> dict[str, list[tuple[Path, NoteFrontmatter | None, str, dict]]]:
    """Build id → [(path, fm_or_None, body, raw_dict)] index scanning top-level files.

    When ``skip_invalid=True`` (default for walk_connections / list_notes),
    entries that fail validation are omitted.
    When ``skip_invalid=False`` (for read_note), all parseable files are included
    so that mutation ops can reach the revalidation barrier in _write_note_file.
    """
    index: dict[str, list[tuple[Path, NoteFrontmatter | None, str, dict]]] = {}
    for path in iter_note_files(root):
        try:
            fm_dict, body = parse_frontmatter(path)
        except (ValueError, yaml.YAMLError):
            continue
        fm_obj, errors = validate_note_frontmatter(fm_dict)
        if skip_invalid and (errors or fm_obj is None):
            continue
        # Use the raw id from the dict so we can index even invalid-fm files
        note_id = fm_dict.get("id")
        if not note_id or not isinstance(note_id, str):
            continue
        index.setdefault(note_id, []).append((path, fm_obj, body, fm_dict))
    return index


def read_note(root: Path, note_id: str) -> tuple[Path, NoteFrontmatter, str]:
    """Find and return (path, fm, body) for the note with ``note_id``.

    Raises ``NoteNotFound`` if absent, ``AmbiguousNoteId`` if duplicate ids.
    Only returns notes with valid frontmatter (invalid ones are skipped).
    For mutation ops that need to detect invalid-on-disk state, use _raw_read_note.
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
    """Like read_note but loads even files with invalid frontmatter.

    Used by mutation ops so that _write_note_file's revalidation can raise
    NoteValidationError instead of silently skipping corrupted files.
    """
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
    """Return outgoing neighbour ids from ``fm`` for the given edge types."""
    neighbours: list[str] = []
    if "concepts" in edge_types:
        neighbours.extend(fm.concepts)
    if "references" in edge_types:
        neighbours.extend(fm.references)
    if "exercises" in edge_types:
        neighbours.extend(fm.exercises)
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

    ``edge_types`` is a subset of ``{'concepts', 'references', 'exercises', 'wikilinks'}``.
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
) -> NoteFrontmatter:
    """Add and/or remove tags on the note with ``note_id``.

    Idempotent: adding an existing tag is a no-op; removing an absent tag is a no-op.
    Re-validates before write. Returns the updated ``NoteFrontmatter``.
    Raises ``NoteValidationError`` if the on-disk frontmatter is already invalid.
    """
    path, fm, body, raw_dict = _raw_read_note(root, note_id)

    # If frontmatter was already invalid on disk, fail before mutating
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
    return new_fm


def add_link(
    root: Path,
    note_id: str,
    *,
    concept: str | None = None,
    reference: str | None = None,
    exercise: str | None = None,
) -> NoteFrontmatter:
    """Append an entry to one of ``concepts``/``references``/``exercises`` (idempotent).

    Exactly one of concept/reference/exercise must be non-None (caller validates).
    Re-validates before write. Returns the updated ``NoteFrontmatter``.
    Raises ``NoteValidationError`` if the on-disk frontmatter is already invalid.
    """
    path, fm, body, raw_dict = _raw_read_note(root, note_id)
    if fm is None:
        _, errors = validate_note_frontmatter(raw_dict)
        raise NoteValidationError(
            f"Frontmatter of {note_id!r} is already invalid: {'; '.join(errors)}"
        )

    if concept is not None:
        new_concepts = (
            tuple(list(fm.concepts) + [concept])
            if concept not in fm.concepts
            else fm.concepts
        )
        new_fm = dataclasses.replace(fm, concepts=new_concepts)
    elif reference is not None:
        new_refs = (
            tuple(list(fm.references) + [reference])
            if reference not in fm.references
            else fm.references
        )
        new_fm = dataclasses.replace(fm, references=new_refs)
    else:  # exercise
        new_exs = (
            tuple(list(fm.exercises) + [exercise])
            if exercise not in fm.exercises
            else fm.exercises
        )
        new_fm = dataclasses.replace(fm, exercises=new_exs)

    _write_note_file(path, new_fm, body)
    return new_fm


def resolve_workspace_root(start: Path) -> Path:
    """Walk up from ``start`` looking for config.yaml or .git.

    Falls back to ``start`` (CWD) with a stderr warning if neither is found.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "config.yaml").exists() or (candidate / ".git").exists():
            return candidate
    print(
        f"[WARN] No config.yaml or .git found above {start}; "
        "using CWD as workspace root.",
        file=sys.stderr,
    )
    return start
