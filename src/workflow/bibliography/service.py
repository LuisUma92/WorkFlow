"""workflow.bibliography.service — shared bibliography lookup helpers.

Public surface used by prisma, content, and exercise modules.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from workflow.db.models.bibliography import BibAuthor, BibEntry

__all__ = ["BibKeyAmbiguous", "get_bib_entry_by_bibkey"]


class BibKeyAmbiguous(Exception):
    """Raised when multiple BibEntry rows share the same bibkey.

    This indicates a data integrity problem that must be resolved at the
    DB layer (e.g., duplicate imports). Callers should not silently
    swallow this; surface it so the operator can deduplicate.
    """


def _bib_entry_options() -> list:
    """Standard eager-load options for BibEntry queries."""
    return [
        selectinload(BibEntry.author_links).selectinload(BibAuthor.author),
        selectinload(BibEntry.author_links).selectinload(BibAuthor.author_type),
    ]


def get_bib_entry_by_bibkey(session: Session, bibkey: str) -> BibEntry | None:
    """Look up a BibEntry by its bibkey with eager-loaded author relationships.

    Contract:
    - 0 matching rows → returns ``None``  (back-compat for callers that treat
      a missing entry as a soft error).
    - 1 matching row  → returns that ``BibEntry``.
    - 2+ matching rows → raises ``BibKeyAmbiguous`` so the caller knows the
      data layer has a duplicate that must be resolved before use.

    Args:
        session: Active SQLAlchemy session.
        bibkey: The citation key to look up (case-sensitive).

    Returns:
        The matching ``BibEntry``, or ``None`` if not found.

    Raises:
        BibKeyAmbiguous: When more than one row matches *bibkey*.
    """
    stmt = (
        select(BibEntry)
        .options(*_bib_entry_options())
        .where(BibEntry.bibkey == bibkey)
    )
    rows = list(session.scalars(stmt).all())

    if len(rows) == 0:
        return None
    if len(rows) == 1:
        return rows[0]
    raise BibKeyAmbiguous(
        f"Multiple BibEntry rows match bibkey {bibkey!r}; "
        "disambiguate at DB layer."
    )
