"""DB → BibTeX/BibLaTeX export for PRISMA systematic review (P2 + P3).

Reverse of ``importer.py``: query BibEntry rows (optionally filtered by
keyword / review status) and emit valid BibTeX or BibLaTeX.

Dialect support (ADR-0019 Phase 3):
- ``dialect="biblatex"`` (default): emit canonical biblatex field names
  (journaltitle, location, institution, annotation, notes, date, …) and
  biblatex entry types as-is.
- ``dialect="bibtex"``: reverse-map biblatex field names to bibtex aliases
  via :func:`workflow.bibliography.dialect.to_bibtex`, downgrade
  biblatex-only entry types to the nearest bibtex equivalent, and split
  the ``date`` column back to ``year`` / ``month``.

The per-entry rendering surface now lives in the foundation module
``workflow.bibliography.render`` (Wave A — A5, ADR-0020). The private names
below are thin re-export aliases kept for backward compatibility; new callers
should import from ``workflow.bibliography.render`` directly.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from workflow.bibliography import render as _render
from workflow.db.models.bibliography import (
    BibEntry,
    BibKeyword,
    ReviewRecord,
)

# Backward-compat re-export shims for the rendering surface relocated to
# ``workflow.bibliography.render`` (Wave A — A5, ADR-0020). These are the SAME
# objects as the public render functions; new callers should import from
# ``workflow.bibliography.render`` directly.
_entry_to_biblatex = _render.entry_to_biblatex
_entry_to_bibtex = _render.entry_to_bibtex
_biblatex_field_pairs = _render.biblatex_field_pairs
_bibtex_field_pairs = _render.bibtex_field_pairs

# The ``_entry_to_*`` / ``_*_field_pairs`` aliases above are deliberately NOT
# in ``__all__`` (they are private re-export shims, available as module
# attributes for backward compatibility, not part of the public ``import *``
# surface — the public surface is ``workflow.bibliography.render``).
__all__ = ["export_bib_entries", "ReviewStatus"]

Dialect = Literal["biblatex", "bibtex"]
ReviewStatus = Literal["included", "excluded", "pending"]


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _status_filter(
    stmt: Select[tuple[BibEntry]],
    keyword_id: int,
    status: ReviewStatus | None,
) -> Select[tuple[BibEntry]]:
    stmt = stmt.join(ReviewRecord, ReviewRecord.bib_entry_id == BibEntry.id).where(
        ReviewRecord.keyword_id == keyword_id
    )
    if status == "included":
        stmt = stmt.where(ReviewRecord.included == 1)
    elif status == "excluded":
        stmt = stmt.where(ReviewRecord.included == 0)
    elif status == "pending":
        stmt = stmt.where(ReviewRecord.included.is_(None))
    return stmt


def _fetch_entries(
    session: Session,
    keyword_id: int | None,
    status: ReviewStatus | None,
) -> list[BibEntry]:
    stmt = select(BibEntry)
    if keyword_id is not None:
        stmt = _status_filter(stmt, keyword_id, status)
    stmt = stmt.order_by(BibEntry.id)
    return list(session.scalars(stmt).unique().all())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_bib_entries(
    session: Session,
    keyword_id: int | None = None,
    status: ReviewStatus | None = None,
    dialect: Dialect = "biblatex",
    *,
    resolve_xref: bool = False,
) -> str:
    """Return a bib string for matching entries.

    With no filters, exports all BibEntries. ``status`` requires
    ``keyword_id``; callers must enforce that (the CLI layer does).
    Raises ``ValueError`` if ``keyword_id`` references a missing keyword.

    :param dialect: ``"biblatex"`` (default) for canonical biblatex output,
        ``"bibtex"`` for a bibtex-compatible downgrade.
    :param resolve_xref: when True, inline fields inherited from resolved
        crossref/xdata parents and suppress those pointer fields (ADR-0019 A4,
        decision D2). When False (default), relation fields round-trip verbatim.
    """
    if dialect not in ("biblatex", "bibtex"):
        raise ValueError(f"Unknown dialect {dialect!r}; use 'biblatex' or 'bibtex'")

    if keyword_id is not None:
        kw = session.get(BibKeyword, keyword_id)
        if kw is None:
            raise ValueError(f"keyword_id={keyword_id} not found")

    entries = _fetch_entries(session, keyword_id, status)

    formatter = _entry_to_biblatex if dialect == "biblatex" else _entry_to_bibtex
    return "\n\n".join(formatter(e, resolve_xref=resolve_xref) for e in entries)
