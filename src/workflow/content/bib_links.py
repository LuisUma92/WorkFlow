"""workflow.content.bib_links — bib-link helpers for Content entries.

Owns: _resolve_bib_entry, link_bib_to_content, list_bib_links,
unlink_bib_from_content, and the bib-link error classes.

Depends on workflow.content.service (base error + ContentNotFound) and
workflow.bibliography.service (hardened lookup helper).
One-directional: service.py must NOT import from this module.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from workflow.bibliography.service import (
    BibKeyAmbiguous as BibBibKeyAmbiguous,
    get_bib_entry_by_bibkey,
)
from workflow.content.service import (
    ContentNotFound,
    ContentServiceError,
    EntityNotFoundError,
    UniquenessError,
)
from workflow.db.errors import AmbiguousLookupError
from workflow.db.models.bibliography import BibContent, BibEntry
from workflow.db.models.knowledge import Content

__all__ = [
    "BibEntryNotFound",
    "BibKeyAmbiguous",
    "BibLinkNotFound",
    "BibLinkAlreadyExists",
    "link_bib_to_content",
    "list_bib_links",
    "unlink_bib_from_content",
]


class BibEntryNotFound(EntityNotFoundError):
    pass


class BibKeyAmbiguous(ContentServiceError, AmbiguousLookupError):
    """Raised when a bibkey lookup hits 2+ rows at the content-service boundary."""


class BibLinkNotFound(ContentServiceError):
    pass


class BibLinkAlreadyExists(UniquenessError):
    pass


def _resolve_bib_entry(session: Session, bibkey: str) -> BibEntry:
    """Resolve a bibkey to exactly one BibEntry row.

    Delegates to the hardened foundation helper.
    Raises BibEntryNotFound on zero matches, BibKeyAmbiguous on 2+.
    """
    try:
        entry = get_bib_entry_by_bibkey(session, bibkey)
    except BibBibKeyAmbiguous as exc:
        raise BibKeyAmbiguous(
            f"Multiple BibEntry rows match bibkey {bibkey!r}; disambiguate at DB layer."
        ) from exc
    if entry is None:
        raise BibEntryNotFound(f"BibEntry with bibkey {bibkey!r} not found.")
    return entry


def link_bib_to_content(
    session: Session,
    *,
    content_id: int,
    bibkey: str,
    chapter_number: int,
    section_number: int,
    first_page: int,
    last_page: int,
    first_exercise: int | None = None,
    last_exercise: int | None = None,
) -> BibContent:
    """Link a BibEntry (by bibkey) to a Content entry."""
    content = session.get(Content, content_id)
    if content is None:
        raise ContentNotFound(f"Content id={content_id} not found.")

    bib = _resolve_bib_entry(session, bibkey)

    existing = session.get(BibContent, (bib.id, content_id))
    if existing is not None:
        raise BibLinkAlreadyExists(
            f"BibEntry {bibkey!r} is already linked to content id={content_id}."
        )

    bc = BibContent(
        bib_entry_id=bib.id,
        content_id=content_id,
        chapter_number=chapter_number,
        section_number=section_number,
        first_page=first_page,
        last_page=last_page,
        first_exercise=first_exercise,
        last_exercise=last_exercise,
    )
    session.add(bc)
    return bc


def list_bib_links(
    session: Session,
    *,
    content_id: int,
) -> list[BibContent]:
    """List BibContent rows for a content entry (with eager-loaded bib_entry)."""
    q = (
        select(BibContent)
        .where(BibContent.content_id == content_id)
        .options(joinedload(BibContent.bib_entry))
    )
    return list(session.scalars(q).all())


def unlink_bib_from_content(
    session: Session,
    *,
    content_id: int,
    bibkey: str,
) -> None:
    """Remove the BibContent link between a bibkey and a Content entry."""
    bib = _resolve_bib_entry(session, bibkey)

    bc = session.get(BibContent, (bib.id, content_id))
    if bc is None:
        raise BibLinkNotFound(
            f"No link between bibkey {bibkey!r} and content id={content_id}."
        )
    session.delete(bc)
