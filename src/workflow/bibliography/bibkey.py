"""Calculated bibkey generation for bibliography entries (ADR-0019, Phase 1).

Pure functions — no DB access, no I/O.

Format (LOCKED):
  Book-like:   <surname:lc><year:04d>[V<volume:02d>]E<edition:02d>
  Article-like: <surname:lc><year:04d>[V<volume:02d>]
  (V segment only when volume is present and numeric.)

Surname rules:
  - Strip von-particle: use ``name_prefix`` when provided; otherwise strip a
    leading all-lowercase word from the surname itself.
  - Strip accents → ASCII via NFKD + drop combining marks.
  - Keep ``[a-z]`` only, lowercased.

Fallbacks (LOCKED):
  - Missing/None year  → ``0000``
  - Missing author     → ``anon``
  - Non-numeric volume → absent (omit V segment)
  - Book missing edition → ``E01``
  - Article missing volume → absent (omit V segment)
"""

from __future__ import annotations

import re
import unicodedata

from workflow.bibliography.dialect import classify_entry_type

__all__ = [
    "calculate_bibkey",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    """Decompose unicode, drop combining marks, return ASCII-only chars."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _normalize_surname(surname: str | None, name_prefix: str | None) -> str:
    """Return the normalised surname token for bibkey construction.

    1. If *name_prefix* is provided (the von-particle, e.g. ``"van"``) the
       surname is used as-is (the particle is already separated).
    2. If no *name_prefix* is given, strip any leading all-lowercase word from
       *surname* (e.g. ``"van Beethoven"`` → ``"Beethoven"``).
    3. Strip accents → ASCII, keep ``[a-z]`` only, lowercase.
    """
    if surname is None:
        return "anon"

    # Determine the base surname (particle already handled or strip inline).
    if name_prefix:
        # Particle is already in name_prefix; surname itself is the real family name.
        base = surname
    else:
        # Strip a leading all-lowercase particle from the surname string.
        # "van Beethoven" → "Beethoven"; "Müller" → "Müller"
        parts = surname.split(None, 1)
        if len(parts) == 2 and parts[0] == parts[0].lower() and parts[0].isalpha():
            base = parts[1]
        else:
            base = surname

    ascii_base = _strip_accents(base)
    letters_only = re.sub(r"[^a-z]", "", ascii_base.lower())
    return letters_only if letters_only else "anon"


def _coerce_volume(volume: object) -> int | None:
    """Extract an integer from *volume*, or return ``None`` if no digits found.

    Accepts int, str (``"3"``, ``"II"``, ``"3rd"``), or None.
    Non-numeric strings (``"II"``) → ``None`` (absent).
    """
    if volume is None:
        return None
    digits = re.sub(r"\D", "", str(volume))
    if not digits:
        return None
    return int(digits)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_bibkey(
    *,
    surname: str | None,
    year: int | None,
    volume: object = None,
    edition: int | None = None,
    entry_type: str | None = None,
    name_prefix: str | None = None,
) -> str:
    """Return the canonical calculated bibkey for a bibliography entry.

    Parameters
    ----------
    surname:
        First author's last name (``Author.last_name``).  ``None`` → ``"anon"``.
    year:
        Publication year (``BibEntry.year`` as int).  ``None`` → ``0000``.
    volume:
        Volume string or int (``BibEntry.volume``).  Non-numeric / ``None`` →
        V segment omitted.
    edition:
        Edition integer (``BibEntry.edition``).  Only used for book-like types.
        ``None`` → ``E01``.
    entry_type:
        BibTeX/BibLaTeX entry type (``BibEntry.entry_type``).  Drives book vs
        article form via :func:`~workflow.bibliography.dialect.classify_entry_type`.
        ``None`` / unknown → article form.
    name_prefix:
        Von-particle (``Author.name_prefix``).  When provided the raw *surname*
        is taken as the family name; when absent the particle is stripped inline
        from *surname* if present.

    Returns
    -------
    str
        Calculated bibkey, e.g. ``"knuth1997V03E03"``, ``"einstein1905V17"``,
        ``"beethoven2001E01"``, ``"smith2020"``.
    """
    # 1. Surname token
    surname_tok = _normalize_surname(surname, name_prefix)

    # 2. Year token
    year_tok = f"{year:04d}" if year is not None else "0000"

    # 3. Volume token (shared between book and article forms)
    vol_int = _coerce_volume(volume)
    vol_seg = f"V{vol_int:02d}" if vol_int is not None else ""

    # 4. Classification
    kind = classify_entry_type(entry_type)  # "book" | "article"

    if kind == "book":
        ed_int = edition if edition is not None else 1
        return f"{surname_tok}{year_tok}{vol_seg}E{ed_int:02d}"
    else:
        # Article form: <surname><year>[V<vol>]
        return f"{surname_tok}{year_tok}{vol_seg}"
