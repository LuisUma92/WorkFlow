"""DB → BibTeX export for PRISMA systematic review (P2).

Reverse of ``importer.py``: query BibEntry rows (optionally filtered by
keyword / review status) and emit valid BibTeX.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import (
    BibEntry,
    BibKeyword,
    ReviewRecord,
)
from workflow.prisma.importer import TRANSLATED_BIB_KEYS

__all__ = ["export_bib_entries", "ReviewStatus"]

ReviewStatus = Literal["included", "excluded", "pending"]

# Model column → BibTeX field name (used on export).
_MODEL_TO_BIB_KEYS: dict[str, str] = dict(TRANSLATED_BIB_KEYS)

_SKIPPED_MODEL_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "isn_type_id",
    }
)

_SAFE_BIBKEY_RE = re.compile(r"^[A-Za-z0-9_:\-]+$")
_SAFE_ETYPE_RE = re.compile(r"^[A-Za-z]+$")


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


def _join_authors(bib_entry: BibEntry, author_type_name: str) -> str | None:
    parts: list[str] = []
    links = sorted(
        (
            link
            for link in bib_entry.author_links
            if link.author_type and link.author_type.type_of_author == author_type_name
        ),
        key=lambda link: (not link.first_author, link.id),
    )
    for link in links:
        a = link.author
        if a is None:
            continue
        first = (a.first_name or "").strip()
        last = (a.last_name or "").strip()
        if first and last:
            parts.append(f"{last}, {first}")
        elif last:
            parts.append(f"{{{last}}}")
        elif first:
            parts.append(first)
    return " and ".join(parts) if parts else None


def _strip_braces(s: str) -> str:
    """Remove raw ``{`` / ``}`` so values can't break out of the wrapper."""
    return s.replace("{", "").replace("}", "")


def _render_value(val: object) -> str:
    """Render a column value as a BibTeX-safe brace-free string."""
    if isinstance(val, date):
        # Year-only imports round-trip as year-only if month/day are defaults.
        if val.month == 1 and val.day == 1:
            return str(val.year)
        return val.isoformat()
    return _strip_braces(str(val))


def _safe_bibkey(raw: str | None, fallback_id: int) -> str:
    candidate = (raw or "").strip()
    if candidate and _SAFE_BIBKEY_RE.match(candidate):
        return candidate
    return f"entry{fallback_id}"


def _safe_etype(raw: str | None) -> str:
    candidate = (raw or "").strip()
    if candidate and _SAFE_ETYPE_RE.match(candidate):
        return candidate
    return "misc"


def _field_pairs(entry: BibEntry) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for col in entry.__table__.columns:
        name = col.name
        if name in _SKIPPED_MODEL_FIELDS:
            continue
        if name in ("entry_type", "bibkey"):
            continue
        val = getattr(entry, name, None)
        if val is None or val == "":
            continue
        bib_key = _MODEL_TO_BIB_KEYS.get(name) or name
        pairs.append((bib_key, _render_value(val)))
    return pairs


def _entry_to_bibtex(entry: BibEntry) -> str:
    etype = _safe_etype(entry.entry_type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role)
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    for key, val in _field_pairs(entry):
        lines.append(f"  {key} = {{{val}}},")

    lines.append("}")
    return "\n".join(lines)


def export_bib_entries(
    session: Session,
    keyword_id: int | None = None,
    status: ReviewStatus | None = None,
) -> str:
    """Return a BibTeX string for matching entries.

    With no filters, exports all BibEntries. ``status`` requires
    ``keyword_id``; callers must enforce that (the CLI layer does).
    Raises ``ValueError`` if ``keyword_id`` references a missing keyword.
    """
    if keyword_id is not None:
        kw = session.get(BibKeyword, keyword_id)
        if kw is None:
            raise ValueError(f"keyword_id={keyword_id} not found")

    entries = _fetch_entries(session, keyword_id, status)
    return "\n\n".join(_entry_to_bibtex(e) for e in entries)
