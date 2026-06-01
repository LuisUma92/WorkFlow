"""BibTeX ↔ BibLaTeX field-name translation.

This is the ONE canonical place where BibTeX-alias → BibLaTeX-native name
translation lives (ADR-0019).  No DB imports; pure functions only.
"""

from __future__ import annotations

import warnings

__all__ = ["BIBTEX_TO_BIBLATEX", "to_biblatex", "to_bibtex"]

# Canonical alias map: bibtex field name → biblatex field name.
# Keys that are already biblatex-native (no alias) are NOT listed here.
# The importer's legacy "journal → journaltitle" bridge is subsumed here.
BIBTEX_TO_BIBLATEX: dict[str, str] = {
    "journal": "journaltitle",
    "address": "location",
    "school": "institution",
    "annote": "annotation",
    "note": "notes",
}

# Inverse map — derived once at import time.
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
