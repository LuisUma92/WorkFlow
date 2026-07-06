"""Service function for `workflow notes capture` (Wave 1 Phase 1).

Creates a new Markdown note directly under the vault root — FLAT layout,
no type subdirectory (locked decision 2026-07-05: note type lives in
frontmatter/DB metadata, directories are not semantic). Filename follows the
zettel_id format's own convention (``workflow notes enums --json`` →
``zettel_id_format.filename_convention``): ``<zettel_id>-<slug>.md``.

After the file is written, the note is registered in the DB via
``sync_note_files`` (Wave 0 D1 extraction) — the same Pass 1-5 pipeline
``notes sync`` uses for the whole vault, applied to exactly the one new file.

Frontmatter is dumped from the raw dict (not ``_fm_to_yaml``) so keys like
``bibkey`` — which the shared serializer does not emit — survive intact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from workflow.concept.service import resolve_concepts
from workflow.notes.ids import generate_zettel_id
from workflow.notes.sync import sync_note_files
from workflow.validation.schemas import validate_note_frontmatter
from workflow.vault.paths import resolve_vault_root

__all__ = ["CaptureResult", "CaptureValidationError", "capture_note"]

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class CaptureValidationError(Exception):
    """Raised before any file is written.

    Covers both frontmatter validation failures and a ``strict=True`` unknown
    concept slug — capture is transactional: nothing is written to disk or
    the DB in either case (mirrors ``notes sync --strict-concepts``'s
    all-or-nothing rule).
    """


@dataclass(frozen=True)
class CaptureResult:
    """Result of a successful ``capture_note`` call."""

    note_path: Path
    zettel_id: str
    created: bool
    issues: tuple[dict, ...] = ()


def _slugify(title: str) -> str:
    """Lowercase, hyphen-join *title* into a filesystem-safe slug.

    Collapses any run of non ``[a-z0-9]`` characters into a single hyphen and
    strips leading/trailing hyphens. Falls back to ``"note"`` when the title
    has no ASCII-alphanumeric content at all.
    """
    slug = _SLUG_RE.sub("-", title.strip().lower()).strip("-")
    return slug or "note"


def capture_note(
    session: Session,
    *,
    title: str,
    note_type: str = "fleeting",
    tags: list[str] | None = None,
    concepts: list[str] | None = None,
    bibkey: str | None = None,
    vault_root: Path | None = None,
    strict: bool = False,
) -> CaptureResult:
    """Create a note in the vault (flat layout) and register it via sync.

    Args:
        session: Active SQLAlchemy session (used for concept resolution and
            passed through to ``sync_note_files``; committed on success).
        title: Note title; also seeds the filename slug.
        note_type: One of ``fleeting`` (default), ``literature``, ``permanent``.
        tags: Tag names for ``frontmatter.tags`` (materialized as Tag/NoteTag
            rows by ``sync_note_files``).
        concepts: Concept slugs for ``frontmatter.concepts``. Resolved via
            ``resolve_concepts`` (slug-only, ITEP-0012 decision #18) up front
            to fail fast under ``strict=True``; the actual NoteConcept rows
            are created by ``sync_note_files`` from the written frontmatter.
        bibkey: Optional bibliography key written to ``frontmatter.bibkey``.
        vault_root: Override vault root (default: ``resolve_vault_root()``).
        strict: When True, an unresolved concept slug raises before any write.
            When False (default), unresolved slugs come back as warning issues
            and the note is still created without a NoteConcept row for that
            slug (matches ``notes sync``'s lenient convention).

    Returns:
        CaptureResult with the new note's path, zettel_id, ``created=True``,
        and any concept-resolution warning issues.

    Raises:
        FileExistsError: if the destination path already exists (capture
            never overwrites an existing note).
        CaptureValidationError: on frontmatter validation failure, or on a
            strict unresolved concept slug (transactional — nothing written).
    """
    tags = list(tags or [])
    concepts = list(concepts or [])
    root = vault_root if vault_root is not None else resolve_vault_root()

    zettel_id = generate_zettel_id()
    path = root / f"{zettel_id}-{_slugify(title)}.md"

    if path.exists():
        raise FileExistsError(f"Note destination already exists: {path}")

    # Resolve concepts BEFORE any write — strict failures must leave no trace.
    issues: list[dict] = []
    if concepts:
        _found, issues = resolve_concepts(concepts, session, strict=strict)
        if strict and any(i["severity"] == "error" for i in issues):
            raise CaptureValidationError(
                "; ".join(
                    i["message"] for i in issues if i["severity"] == "error"
                )
            )

    fm_dict: dict = {
        "id": zettel_id,
        "title": title,
        "type": note_type,
        "tags": tags,
        "concepts": concepts,
        "references": [],
        "exercises": [],
        "images": [],
        "created": date.today().isoformat(),
    }
    if bibkey:
        fm_dict["bibkey"] = bibkey

    fm_obj, errors = validate_note_frontmatter(fm_dict)
    if errors or fm_obj is None:
        raise CaptureValidationError(
            "Frontmatter validation failed: " + "; ".join(errors)
        )

    root.mkdir(parents=True, exist_ok=True)
    fm_yaml = yaml.safe_dump(fm_dict, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm_yaml}---\n", encoding="utf-8")

    sync_note_files([path], session, strict_concepts=strict)
    session.commit()

    return CaptureResult(
        note_path=path,
        zettel_id=zettel_id,
        created=True,
        issues=tuple(issues),
    )
