"""BibTeX ↔ BibLaTeX field-name and entry-type translation.

This is the ONE canonical place where BibTeX-alias → BibLaTeX-native name
translation lives (ADR-0019).  No DB imports; pure functions only.
"""

from __future__ import annotations

import warnings

__all__ = [
    "BIBTEX_TO_BIBLATEX",
    "BIBLATEX_TO_BIBTEX_TYPES",
    "to_biblatex",
    "to_bibtex",
    "downgrade_entry_type",
    "classify_entry_type",
]

# Canonical alias map: bibtex field name → biblatex field name.
# Keys that are already biblatex-native (no alias) are NOT listed here.
# The importer's legacy "journal → journaltitle" bridge is subsumed here.
BIBTEX_TO_BIBLATEX: dict[str, str] = {
    # Standard BibTeX aliases
    "journal": "journaltitle",
    "address": "location",
    "school": "institution",
    "annote": "annotation",
    "note": "notes",
    # arXiv / JabRef / extended aliases
    "archiveprefix": "eprinttype",
    "hyphenation": "langid",
    "key": "sortkey",
    "pdf": "file",
    "primaryclass": "eprintclass",
    # PubMed identifier alias (JabRef/Zotero export as ``pmid``)
    "pmid": "pubmedid",
}

# Inverse map — derived once at import time.
# INVARIANT: some targets (e.g. ``eprinttype``) are native biblatex BibEntry
# columns. The inverse map therefore rewrites them to their bibtex spelling
# (``archiveprefix``) and MUST only be applied on the *bibtex* export path
# (exporter._bibtex_field_pairs). The biblatex export path must never reverse-map,
# or a biblatex→biblatex round-trip would lose ``eprinttype`` (ADR-0019 §MUST).
_BIBLATEX_TO_BIBTEX: dict[str, str] = {v: k for k, v in BIBTEX_TO_BIBLATEX.items()}


def to_biblatex(fields: dict[str, object]) -> dict[str, object]:
    """Return a NEW dict with BibTeX alias keys replaced by BibLaTeX names.

    Collision rule: if the raw dict contains *both* the bibtex alias key and
    its biblatex target (e.g. both ``journal`` and ``journaltitle``), the
    already-present biblatex value wins and a ``UserWarning`` is emitted.
    The input dict is never mutated.
    """
    out: dict[str, object] = {}
    for key, val in fields.items():
        biblatex_key = BIBTEX_TO_BIBLATEX.get(key, key)
        if biblatex_key != key and biblatex_key in fields:
            # Both alias and target present — biblatex value wins (last-writer loses
            # for the alias); emit warning and skip the alias.
            warnings.warn(
                f"BibTeX field {key!r} conflicts with already-present biblatex "
                f"field {biblatex_key!r}; keeping existing biblatex value.",
                UserWarning,
                stacklevel=2,
            )
            continue
        out[biblatex_key] = val
    return out


def to_bibtex(fields: dict[str, object]) -> dict[str, object]:
    """Return a NEW dict with BibLaTeX field names replaced by BibTeX aliases.

    Inverse of :func:`to_biblatex`.  Only performs the reverse mapping for
    keys that have a known bibtex alias; all other keys pass through unchanged.
    The input dict is never mutated.
    """
    out: dict[str, object] = {}
    for key, val in fields.items():
        out[_BIBLATEX_TO_BIBTEX.get(key, key)] = val
    return out


# ---------------------------------------------------------------------------
# Entry-type downgrade table (biblatex → bibtex).
# Keys are lower-case biblatex entry types; values are bibtex equivalents.
# Types absent from this table pass through unchanged (standard bibtex types).
# ---------------------------------------------------------------------------

BIBLATEX_TO_BIBTEX_TYPES: dict[str, str] = {
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


# Book-like entry types for bibkey classification (ADR-0019, Phase 1).
# Locked set: {book, inbook, incollection, collection} (case-insensitive, leading @ tolerated).
_BOOK_TYPES: frozenset[str] = frozenset({"book", "inbook", "incollection", "collection"})


def classify_entry_type(entry_type: str | None) -> str:
    """Classify a bib entry type as ``"book"`` or ``"article"`` for bibkey generation.

    Book-like types: ``{book, inbook, incollection, collection}`` (case-insensitive;
    a leading ``@`` is tolerated).  Everything else — including ``None``, unknown, or
    article/report/thesis/online — returns ``"article"``.

    Pure function; no DB access.
    """
    if entry_type is None:
        return "article"
    normalised = entry_type.strip().lstrip("@").lower()
    return "book" if normalised in _BOOK_TYPES else "article"


def downgrade_entry_type(entry_type: str, *, subtype: str | None = None) -> str:
    """Downgrade a biblatex entry type to the nearest bibtex equivalent.

    Pure function — no DB access.

    ``@thesis`` is special: if ``subtype`` contains a keyword indicating a
    master's thesis (``master``, ``mathesis``, ``msc``), returns
    ``"mastersthesis"``; otherwise ``"phdthesis"``.

    All other biblatex-only types are looked up in :data:`BIBLATEX_TO_BIBTEX_TYPES`;
    standard bibtex types pass through unchanged.
    """
    lower = entry_type.lower()
    if lower == "thesis":
        if subtype:
            t = subtype.lower()
            if any(kw in t for kw in _MASTERS_KEYWORDS):
                return "mastersthesis"
        return "phdthesis"
    return BIBLATEX_TO_BIBTEX_TYPES.get(lower, entry_type)
