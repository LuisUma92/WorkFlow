"""Service function for `workflow notes promote` (Wave 1 Phase 1).

FLIP-ONLY promotion (locked decision ★d, 2026-07-05 — amends ITEP-0011):
flips the note's ``type:`` to ``permanent`` in the .md frontmatter FIRST
(file-as-truth), then registers the change in the DB via ``sync_note_files``
(which upserts ``Note.note_type`` from the file). The file is NEVER moved or
renamed — flat-layout decision: type lives in metadata, directories are not
semantic.

Allowed transitions: ``fleeting → permanent`` and ``literature → permanent``.
Same-type (including re-promote of an already-permanent note) and any
``permanent → *`` demotion are explicit errors.

The frontmatter rewrite works on the RAW parsed dict (not the
``NoteFrontmatter`` dataclass + ``_fm_to_yaml``) so keys the shared
serializer does not emit — ``bibkey``, ``origin``, PRISMA provenance ids —
survive the flip intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from workflow.notes.service import _raw_read_note
from workflow.notes.sync import sync_note_files
from workflow.validation.schemas import validate_note_frontmatter
from workflow.vault.paths import resolve_vault_root

__all__ = ["PromoteError", "PromoteResult", "promote_note"]

_TARGET_TYPE = "permanent"
_PROMOTABLE_TYPES = frozenset({"fleeting", "literature"})


class PromoteError(Exception):
    """Raised when the requested promotion is not a legal transition."""


@dataclass(frozen=True)
class PromoteResult:
    """Result of a successful ``promote_note`` call."""

    reference: str
    from_type: str
    to_type: str
    note_path: Path


def promote_note(
    session: Session,
    reference: str,
    *,
    vault_root: Path | None = None,
) -> PromoteResult:
    """Promote the note identified by *reference* to ``permanent``.

    The note is resolved against the vault root the same way ``notes show``
    resolves ids (frontmatter ``id:`` lookup via ``_raw_read_note``). The
    frontmatter ``type:`` is rewritten in the file FIRST, then the DB row is
    updated via ``sync_note_files`` (file-as-truth ordering).

    Args:
        session: Active SQLAlchemy session (committed on success).
        reference: Note id (zettel_id / frontmatter ``id:``).
        vault_root: Override vault root (default: ``resolve_vault_root()``).

    Returns:
        PromoteResult with reference, from_type, to_type, and note_path.

    Raises:
        PromoteError: same-type promotion (already permanent) or any other
            type outside {fleeting, literature} — no demote in this verb.
        NoteNotFound / AmbiguousNoteId: from the shared lookup helper.
        ValueError: invalid reference characters (shared ``_validate_id``).
    """
    root = vault_root if vault_root is not None else resolve_vault_root()

    path, _fm, body, raw_dict = _raw_read_note(root, reference)

    from_type = raw_dict.get("type", "permanent")
    if from_type == _TARGET_TYPE:
        raise PromoteError(
            f"Note {reference!r} is already {_TARGET_TYPE!r} — nothing to promote."
        )
    if from_type not in _PROMOTABLE_TYPES:
        raise PromoteError(
            f"Note {reference!r} has type {from_type!r}; only "
            f"{sorted(_PROMOTABLE_TYPES)} can be promoted to {_TARGET_TYPE!r}."
        )

    new_raw = {**raw_dict, "type": _TARGET_TYPE}
    _fm_obj, errors = validate_note_frontmatter(new_raw)
    if errors:
        raise PromoteError(
            f"Cannot promote {reference!r}: frontmatter would be invalid after "
            "the flip: " + "; ".join(errors)
        )

    # File first (file-as-truth), then sync flips Note.note_type in the DB.
    fm_yaml = yaml.safe_dump(new_raw, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm_yaml}---\n{body}", encoding="utf-8")

    sync_note_files([path], session)
    session.commit()

    return PromoteResult(
        reference=reference,
        from_type=from_type,
        to_type=_TARGET_TYPE,
        note_path=path,
    )
