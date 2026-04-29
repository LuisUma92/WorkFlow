"""
ADR ITEP-0008 Phase C: derive ``project_initials`` (PP) for new GeneralProjects.

Priority rules, applied in order until a collision-free 2-letter slug is found
within ``(area_id, year_init)``:

1. Initials of the first two whitespace-separated words.
2. First two letters of the first word.
3. First two letters of the second word.
4. Prompt the user for a manual override (handled by the caller).

Each candidate must be exactly two ASCII letters; non-letter characters are
stripped before length checks. Returned initials are upper-cased.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from workflow.db.models.academic import MainTopic
from workflow.db.models.project import GeneralProject


_LETTER_RE = re.compile(r"[A-Za-z]+")


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def _letter_words(title: str) -> list[str]:
    """Split title into accent-stripped, letters-only words."""
    cleaned = _strip_accents(title)
    return [m.group(0) for m in _LETTER_RE.finditer(cleaned)]


@dataclass(frozen=True)
class InitialsCandidate:
    rule: str  # "word_initials" | "word1_prefix" | "word2_prefix" | "manual"
    value: str  # always 2 uppercase letters or "" if not derivable


def candidates(title: str) -> list[InitialsCandidate]:
    """Return ordered candidates for the four priority rules (excluding manual)."""
    words = _letter_words(title)
    out: list[InitialsCandidate] = []

    if len(words) >= 2:
        v = (words[0][0] + words[1][0]).upper()
        out.append(InitialsCandidate("word_initials", v))
    else:
        out.append(InitialsCandidate("word_initials", ""))

    if words and len(words[0]) >= 2:
        out.append(InitialsCandidate("word1_prefix", words[0][:2].upper()))
    else:
        out.append(InitialsCandidate("word1_prefix", ""))

    if len(words) >= 2 and len(words[1]) >= 2:
        out.append(InitialsCandidate("word2_prefix", words[1][:2].upper()))
    else:
        out.append(InitialsCandidate("word2_prefix", ""))

    return out


def is_taken(session: Session, area_id: int, yy: int, pp: str) -> bool:
    """True iff ``(area_id, yy, pp)`` already identifies a GeneralProject."""
    return (
        session.query(GeneralProject)
        .join(MainTopic, GeneralProject.main_topic_id == MainTopic.id)
        .filter(
            MainTopic.parent_id == area_id,
            GeneralProject.year_init == yy,
            GeneralProject.project_initials == pp,
        )
        .first()
        is not None
    )


def derive_project_initials(
    title: str,
    session: Session,
    area_id: int,
    yy: int,
    *,
    extra_taken: Iterable[str] = (),
) -> InitialsCandidate | None:
    """Apply priority rules and return first non-colliding candidate.

    Returns ``None`` when no automatic rule yields a free slug; the caller
    must then prompt the user (rule ``"manual"``).
    """
    taken = {pp.upper() for pp in extra_taken}
    for cand in candidates(title):
        if not cand.value or len(cand.value) != 2:
            continue
        if cand.value in taken:
            continue
        if is_taken(session, area_id, yy, cand.value):
            continue
        return cand
    return None


_PP_RE = re.compile(r"^[A-Z]{2}$")


def validate_pp(value: str) -> str:
    """Return canonical 2-uppercase-letter form or raise ``ValueError``."""
    upper = value.strip().upper()
    if not _PP_RE.match(upper):
        raise ValueError("project_initials must be exactly two letters A-Z.")
    return upper


def slugify_title(title: str) -> str:
    """Convert a free-text title into a filesystem-safe CamelCase slug.

    >>> slugify_title("Sample Theory")
    'SampleTheory'
    """
    words = _letter_words(title)
    return "".join(w[:1].upper() + w[1:] for w in words)
