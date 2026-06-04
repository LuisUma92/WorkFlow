"""BibEntry → BibLaTeX/BibTeX block rendering (foundation layer, ADR-0020).

Relocated from ``workflow.prisma.exporter`` (Wave A — A5) so the rendering
surface lives in the foundation ``workflow.bibliography`` module rather than
the ``prisma`` feature layer. ``prisma.exporter`` retains thin re-export
aliases for backward compatibility.

This module is a **foundation layer** (ADR-0020): it may depend on
``workflow.bibliography.dialect`` and ``workflow.db.models`` but MUST NOT
import upward from ``workflow.prisma`` or any other feature module.

Public API:
- :func:`entry_to_biblatex` / :func:`entry_to_bibtex` — render a full block.
- :func:`biblatex_field_pairs` / :func:`bibtex_field_pairs` — field tuples.
"""

from __future__ import annotations

import re
from datetime import date

from workflow.bibliography.dialect import downgrade_entry_type as _downgrade_entry_type
from workflow.bibliography.dialect import to_bibtex as _dialect_to_bibtex
from workflow.db.models.bibliography import BibEntry

__all__ = [
    "entry_to_biblatex",
    "entry_to_bibtex",
    "biblatex_field_pairs",
    "bibtex_field_pairs",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Columns never emitted as bib fields (internal/metadata columns).
# ``publication_date`` is a derived Python Date object — never a valid bib field.
_SKIPPED_MODEL_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "isn_type_id",
        "publication_date",
    }
)

# In bibtex dialect the ``date`` column is suppressed; year/month columns
# carry the date information instead.
# ``eventdate`` and ``urldate`` are biblatex-only fields — suppress in bibtex.
_BIBTEX_SUPPRESS_FIELDS: frozenset[str] = frozenset({"date", "eventdate", "urldate"})

_SAFE_BIBKEY_RE = re.compile(r"^[A-Za-z0-9_:\-]+$")
_SAFE_ETYPE_RE = re.compile(r"^[A-Za-z]+$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _join_authors(bib_entry: BibEntry, author_type_name: str) -> str | None:
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


# ---------------------------------------------------------------------------
# Field-pair builders
# ---------------------------------------------------------------------------


def biblatex_field_pairs(entry: BibEntry) -> list[tuple[str, str]]:
    """Return (field_name, rendered_value) pairs for biblatex dialect.

    Emits canonical biblatex field names directly (no name translation).
    Skips internal/metadata columns.
    ``isn`` is emitted under its ISN-type code (``isbn``/``issn``/``ismn``) when
    ``entry.isn_type`` is set; falls back to ``isn`` when the type is unknown.
    Overflow fields from ``bib_extra_field`` are appended last.
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
        if name == "isn":
            field_name = entry.isn_type.code.lower() if entry.isn_type else "isn"
            pairs.append((field_name, _render_value(val)))
        else:
            pairs.append((name, _render_value(val)))
    # Append overflow fields (catalog-known, no first-class column).
    # Skip any overflow row whose field is now a first-class column — the column
    # value (already emitted above) takes precedence; this prevents double-emit
    # during the A1→A3 transition period (read-both, column wins — ADR-0019 A3).
    first_class_cols: frozenset[str] = frozenset(
        col.name for col in entry.__table__.columns
    )
    for ef in entry.extra_fields:
        # Column wins only when it actually holds a value. If the promoted
        # column is NULL (pre-A3 import stored the value only in overflow),
        # fall through and emit the overflow row so data is not lost.
        if ef.field in first_class_cols and getattr(entry, ef.field, None) not in (None, ""):
            continue  # column value already emitted above
        pairs.append((ef.field, _strip_braces(ef.value)))
    return pairs


def bibtex_field_pairs(entry: BibEntry) -> list[tuple[str, str]]:
    """Return (field_name, rendered_value) pairs for bibtex dialect.

    - Reverse-maps biblatex field names to bibtex aliases via
      :func:`~workflow.bibliography.dialect.to_bibtex`.
    - Suppresses ``date``, ``eventdate``, ``urldate`` (bibtex-unsupported).
    - ``isn`` is emitted under its ISN-type code (``isbn``/``issn``/``ismn``)
      when ``entry.isn_type`` is set; falls back to ``isn``.
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
        if name == "isn":
            field_name = entry.isn_type.code.lower() if entry.isn_type else "isn"
            raw[field_name] = val
        else:
            raw[name] = val

    # Append overflow fields before dialect reverse-mapping so aliases are applied.
    # Promoted columns already populated ``raw`` above, so ``ef.field not in raw``
    # makes the column win when it holds a value. When the column is NULL
    # (pre-A3 import stored the value only in overflow), the name is absent from
    # ``raw`` and the overflow value is emitted — read-both back-compat (ADR-0019 A3).
    for ef in entry.extra_fields:
        if ef.field not in raw:
            raw[ef.field] = ef.value

    # Reverse-map biblatex field names → bibtex aliases.
    mapped = _dialect_to_bibtex(raw)

    return [(k, _render_value(v)) for k, v in mapped.items()]


# ---------------------------------------------------------------------------
# Public entry formatters
# ---------------------------------------------------------------------------


def entry_to_biblatex(entry: BibEntry) -> str:
    """Render a BibEntry as a BibLaTeX block (canonical biblatex field names).

    Entry types are emitted as-is (no downgrade).
    Author ``name_prefix`` / ``name_suffix`` are included in the
    ``von Last[, Jr][, First]`` form.
    """
    etype = _safe_etype(entry.entry_type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role)
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    for key, val in biblatex_field_pairs(entry):
        lines.append(f"  {key} = {{{val}}},")

    lines.append("}")
    return "\n".join(lines)


def entry_to_bibtex(entry: BibEntry) -> str:
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
    etype = _downgrade_entry_type(raw_etype, subtype=entry.type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role)
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    field_dict: dict[str, str] = dict(bibtex_field_pairs(entry))

    # When @online is downgraded to @misc, inject howpublished=\url{...}
    # from the first available URL, unless howpublished is already present.
    if raw_etype.lower() == "online" and "howpublished" not in field_dict:
        url_str: str | None = None
        if entry.urls:
            # Prefer main_url=True; fall back to first URL.
            main = next((u for u in entry.urls if u.main_url), None)
            url_str = (main or entry.urls[0]).url_string
        if url_str:
            field_dict["howpublished"] = r"\url{" + _strip_braces(url_str) + "}"

    for key, val in field_dict.items():
        lines.append(f"  {key} = {{{val}}},")

    lines.append("}")
    return "\n".join(lines)
