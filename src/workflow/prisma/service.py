"""PRISMA service layer — query and validation operations.

Business logic for bibliography, keywords, and review records.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from workflow.db.models.bibliography import (
    BibAuthor,
    BibEntry,
    BibKeyword,
    ReviewRecord,
)

# ── Status constants ─────────────────────────────────────────────────────

REVIEW_STATUS = {"included": 1, "excluded": 0, "pending": None}
REVIEW_STATUS_LABELS = {1: "included", 0: "excluded", None: "pending"}


# ── Bibliography ─────────────────────────────────────────────────────────


def _bib_entry_options():
    """Standard eager-load options for BibEntry queries."""
    return [
        selectinload(BibEntry.author_links).selectinload(BibAuthor.author),
        selectinload(BibEntry.author_links).selectinload(BibAuthor.author_type),
    ]


def list_bib_entries(
    session: Session,
    *,
    year: int | None = None,
    entry_type: str | None = None,
) -> list[BibEntry]:
    """List bibliography entries with optional filters."""
    stmt = select(BibEntry).options(*_bib_entry_options())
    if year is not None:
        stmt = stmt.where(BibEntry.year == year)
    if entry_type is not None:
        stmt = stmt.where(BibEntry.entry_type == entry_type)
    stmt = stmt.order_by(BibEntry.year.desc(), BibEntry.title)
    return list(session.scalars(stmt).all())


def get_bib_detail(session: Session, bib_id: int) -> BibEntry | None:
    """Get a single bibliography entry with eager-loaded relationships."""
    stmt = (
        select(BibEntry)
        .where(BibEntry.id == bib_id)
        .options(*_bib_entry_options())
    )
    return session.scalars(stmt).first()


# ── Keywords ─────────────────────────────────────────────────────────────


def list_keywords(session: Session) -> list[BibKeyword]:
    """List all search keywords."""
    stmt = select(BibKeyword).order_by(BibKeyword.id)
    return list(session.scalars(stmt).all())


# ── Reviews ──────────────────────────────────────────────────────────────


def list_reviews(
    session: Session,
    *,
    keyword_id: int,
    status: str | None = None,
) -> tuple[list[ReviewRecord], BibKeyword]:
    """List review records for a keyword, returning records and the keyword.

    Raises ValueError if keyword_id does not exist.
    """
    kw = session.get(BibKeyword, keyword_id)
    if kw is None:
        raise ValueError(f"Keyword with id={keyword_id} not found.")

    stmt = (
        select(ReviewRecord)
        .where(ReviewRecord.keyword_id == keyword_id)
        .options(selectinload(ReviewRecord.bib_entry))
    )

    if status is not None:
        status_val = REVIEW_STATUS.get(status)
        if status == "pending":
            stmt = stmt.where(ReviewRecord.included.is_(None))
        else:
            stmt = stmt.where(ReviewRecord.included == status_val)

    records = list(session.scalars(stmt).all())
    return records, kw
