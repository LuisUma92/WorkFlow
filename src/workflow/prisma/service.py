"""PRISMA service layer — query and validation operations.

Business logic for bibliography, keywords, and review records.
"""

from __future__ import annotations

from typing import TypedDict

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from workflow.db.models.bibliography import (
    Author,
    BibAuthor,
    BibEntry,
    BibKeyword,
    BibTag,
    RationaleOption,
    ReviewRecord,
)

# ── Status constants ─────────────────────────────────────────────────────

REVIEW_STATUS = {"included": 1, "excluded": 0, "pending": None}
REVIEW_STATUS_LABELS = {1: "included", 0: "excluded", None: "pending"}

_INCLUDED = REVIEW_STATUS["included"]
_EXCLUDED = REVIEW_STATUS["excluded"]


class ReviewStats(TypedDict):
    """Per-keyword screening counts for `get_review_stats`."""

    keyword_id: int
    keyword: str
    included: int
    excluded: int
    pending: int
    total: int


class ChecklistItem(TypedDict):
    """Single row in `get_checklist` result."""

    item: str
    satisfied: bool
    detail: str


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
    stmt = select(BibEntry).where(BibEntry.id == bib_id).options(*_bib_entry_options())
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
        if status == "pending":
            stmt = stmt.where(ReviewRecord.included.is_(None))
        elif status == "included":
            stmt = stmt.where(ReviewRecord.included == 1)
        elif status == "excluded":
            stmt = stmt.where(ReviewRecord.included == 0)
        else:
            raise ValueError(f"Unknown status: '{status}'")

    records = list(session.scalars(stmt).all())
    return records, kw


# ── Search ───────────────────────────────────────────────────────────────


def search_bib_entries(
    session: Session,
    *,
    title: str | None = None,
    author: str | None = None,
    year: int | None = None,
) -> list[BibEntry]:
    """Search bibliography entries by title, author name, and/or year.

    Raises ValueError if no filter is provided.
    """
    if title is None and author is None and year is None:
        raise ValueError("At least one search filter is required.")

    stmt = select(BibEntry).options(*_bib_entry_options())

    if title is not None:
        pattern = f"%{title}%"
        stmt = stmt.where(BibEntry.title.ilike(pattern))

    if author is not None:
        pattern = f"%{author}%"
        stmt = stmt.where(
            BibEntry.id.in_(
                select(BibAuthor.bib_entry_id)
                .join(Author, BibAuthor.author_id == Author.id)
                .where(
                    or_(
                        Author.last_name.ilike(pattern),
                        Author.first_name.ilike(pattern),
                    )
                )
            )
        )

    if year is not None:
        stmt = stmt.where(BibEntry.year == year)

    stmt = stmt.order_by(BibEntry.year.desc(), BibEntry.title)
    return list(session.scalars(stmt).all())


# ── Keyword CRUD ─────────────────────────────────────────────────────────


def create_keyword(session: Session, *, text: str) -> BibKeyword:
    """Create a new search keyword. Raises ValueError on duplicate."""
    existing = session.scalars(
        select(BibKeyword).where(BibKeyword.keyword_list == text)
    ).first()
    if existing is not None:
        raise ValueError(f"Keyword '{text}' already exists.")

    kw = BibKeyword(keyword_list=text)
    session.add(kw)
    session.flush()
    return kw


# ── Tag CRUD ─────────────────────────────────────────────────────────────


def list_tags(session: Session) -> list[BibTag]:
    """List all tags."""
    stmt = select(BibTag).order_by(BibTag.id)
    return list(session.scalars(stmt).all())


def create_tag(session: Session, *, text: str) -> BibTag:
    """Create a new tag. Raises ValueError on duplicate."""
    existing = session.scalars(select(BibTag).where(BibTag.tag == text)).first()
    if existing is not None:
        raise ValueError(f"Tag '{text}' already exists.")

    tag = BibTag(tag=text)
    session.add(tag)
    session.flush()
    return tag


# ── Rationale CRUD ───────────────────────────────────────────────────────


def list_rationales(session: Session) -> list[RationaleOption]:
    """List all rationale options."""
    stmt = select(RationaleOption).order_by(RationaleOption.id)
    return list(session.scalars(stmt).all())


def create_rationale(session: Session, *, text: str) -> RationaleOption:
    """Create a new rationale option. Raises ValueError on duplicate."""
    existing = session.scalars(
        select(RationaleOption).where(RationaleOption.rationale_argument == text)
    ).first()
    if existing is not None:
        raise ValueError(f"Rationale '{text}' already exists.")

    opt = RationaleOption(rationale_argument=text)
    session.add(opt)
    session.flush()
    return opt


# ── Screening ────────────────────────────────────────────────────────────


def screen_article(
    session: Session,
    *,
    bib_entry_id: int,
    keyword_id: int,
    include: bool,
    rationale: str | None = None,
) -> ReviewRecord:
    """Screen an article: set included/excluded for a keyword.

    If a pending ReviewRecord exists, updates it. Otherwise creates a new one.
    Raises ValueError if article or keyword not found.
    """
    entry = session.get(BibEntry, bib_entry_id)
    if entry is None:
        raise ValueError(f"BibEntry with id={bib_entry_id} not found.")

    kw = session.get(BibKeyword, keyword_id)
    if kw is None:
        raise ValueError(f"Keyword with id={keyword_id} not found.")

    # Check for existing review record
    stmt = select(ReviewRecord).where(
        ReviewRecord.keyword_id == keyword_id,
        ReviewRecord.bib_entry_id == bib_entry_id,
    )
    rec = session.scalars(stmt).first()

    status_val = REVIEW_STATUS["included" if include else "excluded"]

    if rec is not None:
        if rec.included is not None:
            raise ValueError(
                f"Article {bib_entry_id} already screened as "
                f"'{REVIEW_STATUS_LABELS[rec.included]}' for keyword {keyword_id}."
            )
        rec.included = status_val
        if rationale is not None:
            rec.include_rationale = rationale
    else:
        rec = ReviewRecord(
            keyword_id=keyword_id,
            bib_entry_id=bib_entry_id,
            retrieved=1,
            included=status_val,
            include_rationale=rationale,
        )
        session.add(rec)

    session.flush()
    return rec


# ── Stats (P2) ───────────────────────────────────────────────────────────


def get_review_stats(session: Session, keyword_id: int) -> ReviewStats:
    """Return per-keyword screening counts.

    Issues one aggregate query (``CASE`` over ``included``) so ``total``
    always equals the true row count for the keyword, even if a new
    status value is introduced later. Raises ``ValueError`` if
    ``keyword_id`` does not exist.
    """
    kw = session.get(BibKeyword, keyword_id)
    if kw is None:
        raise ValueError(f"keyword_id={keyword_id} not found")

    stmt = select(
        func.sum(case((ReviewRecord.included == _INCLUDED, 1), else_=0)),
        func.sum(case((ReviewRecord.included == _EXCLUDED, 1), else_=0)),
        func.sum(case((ReviewRecord.included.is_(None), 1), else_=0)),
        func.count(),
    ).where(ReviewRecord.keyword_id == keyword_id)

    row = session.execute(stmt).one()
    included, excluded, pending, total = (int(v or 0) for v in row)

    return ReviewStats(
        keyword_id=kw.id,
        keyword=kw.keyword_list,
        included=included,
        excluded=excluded,
        pending=pending,
        total=total,
    )


# ── Checklist (P2) ───────────────────────────────────────────────────────


def _count_table(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _count_reviews(
    session: Session, keyword_id: int | None, only_decided: bool = False
) -> int:
    stmt = select(func.count()).select_from(ReviewRecord)
    if keyword_id is not None:
        stmt = stmt.where(ReviewRecord.keyword_id == keyword_id)
    if only_decided:
        stmt = stmt.where(ReviewRecord.included.is_not(None))
    return int(session.scalar(stmt) or 0)


def _count_pending(session: Session, keyword_id: int | None) -> int:
    stmt = (
        select(func.count())
        .select_from(ReviewRecord)
        .where(ReviewRecord.included.is_(None))
    )
    if keyword_id is not None:
        stmt = stmt.where(ReviewRecord.keyword_id == keyword_id)
    return int(session.scalar(stmt) or 0)


def _item(label: str, satisfied: bool, detail: str) -> ChecklistItem:
    return ChecklistItem(item=label, satisfied=satisfied, detail=detail)


def _all_decided_detail(n_reviews: int, n_pending: int) -> str:
    if n_reviews == 0:
        return "no records"
    if n_pending > 0:
        return f"{n_pending} pending"
    return "complete"


def get_checklist(
    session: Session, keyword_id: int | None = None
) -> list[ChecklistItem]:
    """Return PRISMA compliance checklist derived from DB state.

    Items 1-3 (keywords / bibliography / screening criteria) always
    reflect global counts across the DB. Items 4-6 (review-record
    items) are scoped to ``keyword_id`` when given; otherwise they
    aggregate across all keywords. Raises ``ValueError`` if
    ``keyword_id`` is provided but does not exist.
    """
    if keyword_id is not None:
        kw = session.get(BibKeyword, keyword_id)
        if kw is None:
            raise ValueError(f"keyword_id={keyword_id} not found")

    n_keywords = _count_table(session, BibKeyword)
    n_bib = _count_table(session, BibEntry)
    n_rationale = _count_table(session, RationaleOption)

    n_reviews = _count_reviews(session, keyword_id)
    n_decided = _count_reviews(session, keyword_id, only_decided=True)
    n_pending = _count_pending(session, keyword_id)

    return [
        _item("Search keywords defined", n_keywords > 0, f"{n_keywords} keywords"),
        _item("Bibliography imported", n_bib > 0, f"{n_bib} entries"),
        _item(
            "Screening criteria defined",
            n_rationale > 0,
            f"{n_rationale} rationale options",
        ),
        _item("Articles retrieved", n_reviews > 0, f"{n_reviews} records"),
        _item("Screening in progress", n_decided > 0, f"{n_decided} decided"),
        _item(
            "All articles decided",
            n_reviews > 0 and n_pending == 0,
            _all_decided_detail(n_reviews, n_pending),
        ),
    ]
