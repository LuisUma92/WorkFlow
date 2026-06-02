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
import warnings

from workflow.bibliography.dialect import classify_entry_type

__all__ = [
    "calculate_bibkey",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Ligature / special-character substitution table applied BEFORE NFKD folding.
# Order matters: longer sequences first where relevant.
_LIGATURE_TABLE: list[tuple[str, str]] = [
    ("ß", "ss"),
    ("æ", "ae"),
    ("œ", "oe"),
    ("ø", "o"),
    ("å", "a"),
    ("ð", "d"),
    ("þ", "th"),
    ("ł", "l"),
]


def _strip_accents(text: str) -> str:
    """Apply ligature substitutions then decompose unicode, drop combining marks."""
    # Apply ligature table on lowercased copy (input is already lowercased by caller)
    for src, dst in _LIGATURE_TABLE:
        text = text.replace(src, dst)
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _normalize_surname(surname: str | None, name_prefix: str | None) -> str:
    """Return the normalised surname token for bibkey construction.

    1. If *name_prefix* is provided (the von-particle, e.g. ``"van"``) the
       surname is used as-is (the particle is already separated).
    2. If no *name_prefix* is given, strip ALL leading all-lowercase tokens from
       *surname* (e.g. ``"van Beethoven"`` → ``"Beethoven"``,
       ``"von der Leyen"`` → ``"Leyen"``).  Single-token names are left intact.
    3. Strip accents → ASCII, keep ``[a-z]`` only, lowercase.
    """
    if surname is None:
        return "anon"

    # Determine the base surname (particle already handled or strip inline).
    if name_prefix:
        # Particle is already in name_prefix; surname itself is the real family name.
        base = surname
    else:
        # Strip ALL leading all-lowercase particles from the surname string.
        # "von der Leyen" → "Leyen"; "van der Berg" → "Berg"; "Müller" → "Müller"
        # Single-token or all-lowercase single name → unchanged.
        tokens = surname.split()
        while len(tokens) >= 2 and tokens[0].isalpha() and tokens[0] == tokens[0].lower():
            tokens = tokens[1:]
        base = " ".join(tokens)

    ascii_base = _strip_accents(base.lower())
    letters_only = re.sub(r"[^a-z]", "", ascii_base)
    if not letters_only:
        warnings.warn(
            f"surname {surname!r} reduced to empty after normalisation; using 'anon'.",
            UserWarning,
            stacklevel=3,
        )
        return "anon"
    return letters_only


def _coerce_volume(volume: object) -> int | None:
    """Extract an integer from *volume*, or return ``None`` if no digits found.

    Accepts int, str (``"3"``, ``"II"``, ``"3rd"``), or None.
    Non-numeric strings (``"II"``) → ``None`` (absent).
    """
    if volume is None:
        return None
    raw = str(volume).strip()
    negative = raw.startswith("-")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    val = int(digits)
    if negative or val <= 0 or val > 9999:
        return None
    return val


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

    # 2. Year token (clamp negatives to 0000; positives > 9999 rendered as-is)
    if year is None:
        year_tok = "0000"
    elif year < 0:
        year_tok = "0000"
    else:
        year_tok = f"{year:04d}"

    # 3. Volume token (shared between book and article forms)
    vol_int = _coerce_volume(volume)
    vol_seg = f"V{vol_int:02d}" if vol_int is not None else ""

    # 4. Classification
    kind = classify_entry_type(entry_type)  # "book" | "article"

    if kind == "book":
        ed_int = edition if (edition is not None and edition > 0) else 1
        return f"{surname_tok}{year_tok}{vol_seg}E{ed_int:02d}"
    else:
        # Article form: <surname><year>[V<vol>]
        return f"{surname_tok}{year_tok}{vol_seg}"
