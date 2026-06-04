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
from workflow.bibliography.inheritance import inherit_crossref, inherit_xdata
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


# Order in which relation kinds are emitted as bib fields.
_RELATION_KINDS: tuple[str, ...] = ("crossref", "xref", "xdata", "related")


def _relation_field_pairs(
    entry: BibEntry,
    kinds: tuple[str, ...] = _RELATION_KINDS,
) -> list[tuple[str, str]]:
    """Return (field, value) pairs reconstructed from ``entry.relations``.

    crossref/xref emit a single target; xdata/related join their targets with
    ``, `` (one BibRelation row per target). Uses ``parent_bibkey`` (the raw
    target) so the round-trip is lossless even for unresolved relations.
    ``kinds`` limits which relation kinds are emitted (used by resolve-xref to
    keep the non-inheriting ``xref``/``related`` pointers while suppressing the
    resolved ``crossref``/``xdata``).
    """
    by_kind: dict[str, list[str]] = {}
    for rel in entry.relations:
        by_kind.setdefault(rel.kind, []).append(rel.parent_bibkey)
    pairs: list[tuple[str, str]] = []
    for kind in kinds:
        keys = by_kind.get(kind)
        if keys:
            pairs.append((kind, ", ".join(_strip_braces(k) for k in keys)))
    return pairs


# Relation kinds that do NOT trigger field inheritance — kept as pointer fields
# even under --resolve-xref.
_NON_INHERITING_KINDS: tuple[str, ...] = ("xref", "related")


def _resolve_inherited_fields(entry: BibEntry) -> dict[str, str]:
    """Compute fields ``entry`` inherits from its resolved crossref/xdata parents.

    One level deep. crossref applies biblatex field remapping; xdata copies
    verbatim. Among multiple relations the first to provide a field wins; the
    caller applies child-wins precedence over the result.
    """
    result: dict[str, str] = {}
    for rel in entry.relations:
        if rel.parent is None:
            continue
        # resolve_xref=False pins one-level inheritance (no grandparent chains).
        parent_fields = dict(biblatex_field_pairs(rel.parent, resolve_xref=False))
        if rel.kind == "crossref":
            inherited = inherit_crossref(
                rel.parent.entry_type, entry.entry_type, parent_fields
            )
        elif rel.kind == "xdata":
            inherited = inherit_xdata(parent_fields)
        else:
            continue
        for key, value in inherited.items():
            result.setdefault(key, value)
    return result


# ---------------------------------------------------------------------------
# Field-pair builders
# ---------------------------------------------------------------------------


def _resolve_xref_extra(
    entry: BibEntry,
    existing: set[str],
) -> list[tuple[str, str]]:
    """resolve-xref tail: inherited fields (child-wins) + xref/related pointers.

    ``existing`` is the set of field names the child already emits; inherited
    fields are added only when absent (child-wins). ``existing`` is mutated.
    """
    out: list[tuple[str, str]] = []
    for key, value in _resolve_inherited_fields(entry).items():
        if key not in existing:
            out.append((key, _strip_braces(value)))
            existing.add(key)
    out.extend(_relation_field_pairs(entry, kinds=_NON_INHERITING_KINDS))
    return out


def _bibtex_column_dict(entry: BibEntry) -> dict[str, object]:
    """Collect biblatex-named column values for the bibtex builder.

    Skips internal/metadata columns and bibtex-unsupported fields; emits ``isn``
    under its ISN-type code.
    """
    raw: dict[str, object] = {}
    for col in entry.__table__.columns:
        name = col.name
        if (
            name in _SKIPPED_MODEL_FIELDS
            or name in ("entry_type", "bibkey")
            or name in _BIBTEX_SUPPRESS_FIELDS
        ):
            continue
        val = getattr(entry, name, None)
        if val is None or val == "":
            continue
        if name == "isn":
            raw[entry.isn_type.code.lower() if entry.isn_type else "isn"] = val
        else:
            raw[name] = val
    return raw


def biblatex_field_pairs(
    entry: BibEntry,
    *,
    resolve_xref: bool = False,
) -> list[tuple[str, str]]:
    """Return (field_name, rendered_value) pairs for biblatex dialect.

    Emits canonical biblatex field names directly (no name translation).
    Skips internal/metadata columns.
    ``isn`` is emitted under its ISN-type code (``isbn``/``issn``/``ismn``) when
    ``entry.isn_type`` is set; falls back to ``isn`` when the type is unknown.
    Overflow fields from ``bib_extra_field`` are appended last.

    When ``resolve_xref`` is True, fields inherited from resolved crossref/xdata
    parents are merged in (child-wins), and the resolved ``crossref``/``xdata``
    pointer fields are suppressed; non-inheriting ``xref``/``related`` pointers
    are kept.
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
        if ef.field in _RELATION_KINDS:
            continue  # relations are emitted from bib_relation, never overflow (A4)
        # Column wins only when it actually holds a value. If the promoted
        # column is NULL (pre-A3 import stored the value only in overflow),
        # fall through and emit the overflow row so data is not lost.
        if ef.field in first_class_cols and getattr(entry, ef.field, None) not in (None, ""):
            continue  # column value already emitted above
        pairs.append((ef.field, _strip_braces(ef.value)))
    if resolve_xref:
        # A4-5: inline inherited crossref/xdata fields (child-wins), suppress
        # resolved pointers, keep xref/related pointers.
        pairs.extend(_resolve_xref_extra(entry, {k for k, _ in pairs}))
    else:
        # A4-4: re-emit all relations verbatim for a lossless round-trip.
        pairs.extend(_relation_field_pairs(entry))
    return pairs


def bibtex_field_pairs(
    entry: BibEntry,
    *,
    resolve_xref: bool = False,
) -> list[tuple[str, str]]:
    """Return (field_name, rendered_value) pairs for bibtex dialect.

    - Reverse-maps biblatex field names to bibtex aliases via
      :func:`~workflow.bibliography.dialect.to_bibtex`.
    - Suppresses ``date``, ``eventdate``, ``urldate`` (bibtex-unsupported).
    - ``isn`` is emitted under its ISN-type code (``isbn``/``issn``/``ismn``)
      when ``entry.isn_type`` is set; falls back to ``isn``.

    When ``resolve_xref`` is True, inherited crossref/xdata fields are merged in
    (child-wins) and the resolved pointer fields are suppressed; non-inheriting
    ``xref``/``related`` pointers are kept.
    """
    raw = _bibtex_column_dict(entry)

    # Append overflow fields before dialect reverse-mapping so aliases are applied.
    # Promoted columns already populated ``raw`` above, so ``ef.field not in raw``
    # makes the column win when it holds a value. When the column is NULL
    # (pre-A3 import stored the value only in overflow), the name is absent from
    # ``raw`` and the overflow value is emitted — read-both back-compat (ADR-0019 A3).
    for ef in entry.extra_fields:
        if ef.field in _RELATION_KINDS:
            continue  # relations are emitted from bib_relation, never overflow (A4)
        if ef.field not in raw:
            raw[ef.field] = ef.value

    if resolve_xref:
        # Inline inherited crossref/xdata fields (child-wins via setdefault),
        # keep only the non-inheriting xref/related pointers (A4-5).
        for key, value in _resolve_inherited_fields(entry).items():
            raw.setdefault(key, value)
        relation_kinds = _NON_INHERITING_KINDS
    else:
        # Re-emit all relations (A4-4). crossref is valid bibtex; xref/xdata/
        # related are biblatex-only but preserved for a lossless downgrade
        # (matches the pre-A4 overflow behaviour).
        relation_kinds = _RELATION_KINDS
    for field_name, value in _relation_field_pairs(entry, kinds=relation_kinds):
        raw.setdefault(field_name, value)

    # Reverse-map biblatex field names → bibtex aliases.
    mapped = _dialect_to_bibtex(raw)

    return [(k, _render_value(v)) for k, v in mapped.items()]


# ---------------------------------------------------------------------------
# Public entry formatters
# ---------------------------------------------------------------------------


def entry_to_biblatex(entry: BibEntry, *, resolve_xref: bool = False) -> str:
    """Render a BibEntry as a BibLaTeX block (canonical biblatex field names).

    Entry types are emitted as-is (no downgrade).
    Author ``name_prefix`` / ``name_suffix`` are included in the
    ``von Last[, Jr][, First]`` form.
    ``resolve_xref`` inlines inherited crossref/xdata fields (see
    :func:`biblatex_field_pairs`).
    """
    etype = _safe_etype(entry.entry_type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role)
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    for key, val in biblatex_field_pairs(entry, resolve_xref=resolve_xref):
        lines.append(f"  {key} = {{{val}}},")

    lines.append("}")
    return "\n".join(lines)


def entry_to_bibtex(entry: BibEntry, *, resolve_xref: bool = False) -> str:
    """Render a BibEntry as a BibTeX block.

    - Downgrades biblatex-only entry types (online→misc, report→techreport,
      thesis→phdthesis/mastersthesis, …).
    - Reverse-maps biblatex field names to bibtex aliases
      (journaltitle→journal, location→address, institution→school,
      annotation→annote, notes→note).
    - Suppresses ``date``; ``year`` / ``month`` carry the date information.
    - Author ``name_prefix`` / ``name_suffix`` emitted in the same
      ``von Last[, Jr][, First]`` form (valid in bibtex).
    ``resolve_xref`` inlines inherited crossref/xdata fields.
    """
    raw_etype = _safe_etype(entry.entry_type)
    etype = _downgrade_entry_type(raw_etype, subtype=entry.type)
    bibkey = _safe_bibkey(entry.bibkey, entry.id)

    lines: list[str] = [f"@{etype}{{{bibkey},"]

    for role in ("author", "editor", "translator"):
        joined = _join_authors(entry, role)
        if joined:
            lines.append(f"  {role} = {{{_strip_braces(joined)}}},")

    field_dict: dict[str, str] = dict(
        bibtex_field_pairs(entry, resolve_xref=resolve_xref)
    )

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
