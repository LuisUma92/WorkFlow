"""Content service — add, list, get, bib-link."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import BibContent, BibEntry
from workflow.db.models.knowledge import Content, Topic
from workflow.prisma.service import get_bib_entry_by_bibkey

__all__ = [
    "ContentServiceError",
    "TopicNotFound",
    "DuplicateContent",
    "BibEntryNotFound",
    "BibKeyAmbiguous",
    "BibLinkNotFound",
    "BibLinkAlreadyExists",
    "ContentNotFound",
    "add_content",
    "list_contents",
    "get_content",
    "link_bib_to_content",
    "list_bib_links",
    "unlink_bib_from_content",
]


class ContentServiceError(Exception):
    pass


class TopicNotFound(ContentServiceError):
    pass


class DuplicateContent(ContentServiceError):
    pass


class BibEntryNotFound(ContentServiceError):
    pass


class BibKeyAmbiguous(ContentServiceError):
    pass


class BibLinkNotFound(ContentServiceError):
    pass


class BibLinkAlreadyExists(ContentServiceError):
    pass


class ContentNotFound(ContentServiceError):
    pass


def add_content(
    session: Session,
    *,
    topic_id: int,
    name: str,
) -> Content:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise TopicNotFound(f"Topic id={topic_id} not found.")

    existing = session.scalars(
        select(Content).where(
            Content.topic_id == topic_id,
            Content.name == name,
        )
    ).first()
    if existing is not None:
        raise DuplicateContent(
            f"Content {name!r} already exists in topic id={topic_id}."
        )

    c = Content(topic_id=topic_id, name=name)
    session.add(c)
    return c


def list_contents(
    session: Session,
    *,
    topic_id: int | None = None,
) -> list[Content]:
    q = select(Content).order_by(Content.id)
    if topic_id is not None:
        q = q.where(Content.topic_id == topic_id)
    return list(session.scalars(q).all())


def get_content(session: Session, content_id: int) -> Content | None:
    return session.get(Content, content_id)


def _resolve_bib_entry(session: Session, bibkey: str):
    """Resolve a bibkey to a single BibEntry; raise on ambiguity or missing."""
    count = session.scalar(
        select(func.count()).select_from(BibEntry).where(BibEntry.bibkey == bibkey)
    )
    if count == 0 or count is None:
        raise BibEntryNotFound(f"BibEntry with bibkey {bibkey!r} not found.")
    if count > 1:
        raise BibKeyAmbiguous(
            f"Multiple BibEntry rows match bibkey {bibkey!r}; disambiguate at DB layer."
        )
    return get_bib_entry_by_bibkey(session, bibkey)


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
    q = select(BibContent).where(BibContent.content_id == content_id)
    return list(session.scalars(q).all())


def unlink_bib_from_content(
    session: Session,
    *,
    content_id: int,
    bibkey: str,
) -> None:
    bib = _resolve_bib_entry(session, bibkey)

    bc = session.get(BibContent, (bib.id, content_id))
    if bc is None:
        raise BibLinkNotFound(
            f"No link between bibkey {bibkey!r} and content id={content_id}."
        )
    session.delete(bc)
