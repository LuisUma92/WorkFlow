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
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from workflow.bibliography.dialect import to_bibtex as _dialect_to_bibtex
from workflow.db.models.bibliography import (
    BibEntry,
    BibKeyword,
    ReviewRecord,
)

__all__ = ["export_bib_entries", "ReviewStatus"]

Dialect = Literal["biblatex", "bibtex"]
ReviewStatus = Literal["included", "excluded", "pending"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Columns never emitted as bib fields.
_SKIPPED_MODEL_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "isn_type_id",
    }
)

# In bibtex dialect the ``date`` column is suppressed; year/month columns
# carry the date information instead.
_BIBTEX_SUPPRESS_FIELDS: frozenset[str] = frozenset({"date"})

_SAFE_BIBKEY_RE = re.compile(r"^[A-Za-z0-9_:\-]+$")
_SAFE_ETYPE_RE = re.compile(r"^[A-Za-z]+$")

# ---------------------------------------------------------------------------
# Entry-type downgrade table (biblatex → bibtex).
# Keys are lower-case biblatex entry types; values are bibtex equivalents.
# Types absent from this table pass through unchanged (standard bibtex types).
# ---------------------------------------------------------------------------
_BIBLATEX_TO_BIBTEX_TYPES: dict[str, str] = {
    # Electronic / web
    "online": "misc",
    "electronic": "misc",
    "www": "misc",
    # Reports
    "report": "techreport",
    # Multi-volume books
    "mvbook": "book",
    "mvcollection": "book",
    "mvproceedings": "proceedings",
    "mvreference": "book",
    # In-container entries
    "inreference": "inbook",
    "suppbook": "inbook",
    "suppcollection": "incollection",
    "suppperiodical": "article",
    # Periodicals
    "periodical": "misc",
    # Patents / other
    "patent": "misc",
    "software": "misc",
    "dataset": "misc",
    # @thesis is handled specially (→ phdthesis or mastersthesis)
}

# Keyword fragments in the ``type`` subfield that indicate a master's thesis.
_MASTERS_KEYWORDS = ("master", "mathesis", "msc")


# ---------------------------------------------------------------------------
# Internal helpers
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


def _join_authors(bib_entry: BibEntry, author_type_name: str, dialect: Dialect) -> str | None:
    """Format author list for a given role.

    Both dialects use the ``von Last, Jr, First`` / ``von Last, First``
    form so that name parts (prefix, suffix) are preserved faithfully.
    Plain ``Last, First`` is used when no prefix/suffix are present.
    """
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
        prefix = (a.name_prefix or "").strip()
        suffix = (a.name_suffix or "").strip()

        # Build the canonical "von Last[, Jr][, First]" form.
        # This is valid in both bibtex and biblatex.
        von_last = f"{prefix} {last}".strip() if prefix else last
        if suffix and first:
            parts.append(f"{von_last}, {suffix}, {first}")
        elif suffix:
            parts.append(f"{von_last}, {suffix}")
        elif first:
            parts.append(f"{von_last}, {first}")
        elif von_last:
            parts.append(f"{{{von_last}}}")
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


def _downgrade_entry_type(entry_type: str, type_subfield: str | None) -> str:
    """Downgrade a biblatex entry type to the nearest bibtex equivalent.

    ``@thesis`` is special: if the ``type`` subfield contains a keyword
    indicating a master's thesis, returns ``mastersthesis``; otherwise
    ``phdthesis``.
    """
    lower = entry_type.lower()
    if lower == "thesis":
        if type_subfield:
            t = type_subfield.lower()
            if any(kw in t for kw in _MASTERS_KEYWORDS):
                return "mastersthesis"
        return "phdthesis"
    return _BIBLATEX_TO_BIBTEX_TYPES.get(lower, entry_type)


def _biblatex_field_pairs(entry: BibEntry) -> list[tuple[str, str]]:
    """Return (field_name, rendered_value) pairs for biblatex dialect.

    Emits canonical biblatex field names directly (no name translation).
    Skips internal/metadata columns.
    """
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
        pairs.append((name, _render_value(val)))
    return pairs


def _bibtex_field_pairs(entry: BibEntry) -> list[tuple[str, str]]:
    """Return (field_name, rendered_value) pairs for bibtex dialect.

    - Reverse-maps biblatex field names to bibtex aliases via
      :func:`~workflow.bibliography.dialect.to_bibtex`.
    - Suppresses ``date`` (bibtex uses ``year`` / ``month`` columns).
    - ``isn`` is emitted as-is (bibtex has no standard isn field, but it
      is preferable to silently dropping it).
    """
    raw: dict[str, object] = {}
    for col in entry.__table__.columns:
        name = col.name
        if name in _SKIPPED_MODEL_FIELDS:
            continue
        if name in ("entry_type", "bibkey"):
            continue
        if name in _BIBTEX_SUPPRESS_FIELDS:
            continue
        val = getattr(entry, name, None)
        if val is None or val == "":
            continue
        raw[name] = val

    # Reverse-map biblatex field names → bibtex aliases.
    mapped = _dialect_to_bibtex(raw)

    return [(k, _render_value(v)) for k, v in mapped.items()]


# ---------------------------------------------------------------------------
# Public entry formatters
# ---------------------------------------------------------------------------


def _entry_to_biblatex(entry: BibEntry) -> str:
    """Render a BibEntry as a BibLaTeX block (canonical biblatex field names).

    Entry types are emitted as-is (no downgrade).
    Author ``name_prefix`` / ``name_suffix`` are included in the
    ``von Last[, Jr][, First]`` form.
    """
    etype = _safe_etype(entry.entry_type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role, dialect="biblatex")
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    for key, val in _biblatex_field_pairs(entry):
        lines.append(f"  {key} = {{{val}}},")

    lines.append("}")
    return "\n".join(lines)


def _entry_to_bibtex(entry: BibEntry) -> str:
    """Render a BibEntry as a BibTeX block.

    - Downgrades biblatex-only entry types (online→misc, report→techreport,
      thesis→phdthesis/mastersthesis, …).
    - Reverse-maps biblatex field names to bibtex aliases
      (journaltitle→journal, location→address, institution→school,
      annotation→annote, notes→note).
    - Suppresses ``date``; ``year`` / ``month`` carry the date information.
    - Author ``name_prefix`` / ``name_suffix`` emitted in the same
      ``von Last[, Jr][, First]`` form (valid in bibtex).
    """
    raw_etype = _safe_etype(entry.entry_type)
    etype = _downgrade_entry_type(raw_etype, entry.type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role, dialect="bibtex")
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    for key, val in _bibtex_field_pairs(entry):
        lines.append(f"  {key} = {{{val}}},")

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_bib_entries(
    session: Session,
    keyword_id: int | None = None,
    status: ReviewStatus | None = None,
    dialect: Dialect = "biblatex",
) -> str:
    """Return a bib string for matching entries.

    With no filters, exports all BibEntries. ``status`` requires
    ``keyword_id``; callers must enforce that (the CLI layer does).
    Raises ``ValueError`` if ``keyword_id`` references a missing keyword.

    :param dialect: ``"biblatex"`` (default) for canonical biblatex output,
        ``"bibtex"`` for a bibtex-compatible downgrade.
    """
    if dialect not in ("biblatex", "bibtex"):
        raise ValueError(f"Unknown dialect {dialect!r}; use 'biblatex' or 'bibtex'")

    if keyword_id is not None:
        kw = session.get(BibKeyword, keyword_id)
        if kw is None:
            raise ValueError(f"keyword_id={keyword_id} not found")

    entries = _fetch_entries(session, keyword_id, status)

    formatter = _entry_to_biblatex if dialect == "biblatex" else _entry_to_bibtex
    return "\n\n".join(formatter(e) for e in entries)
