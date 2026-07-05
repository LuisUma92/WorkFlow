"""Chapter-range filter for ``exercise list --chapter`` (Phase 2b).

``Exercise`` has no ``chapter`` column (ADR-0010 file-as-truth; see
CLAUDE.md's exercise-CLI bullet). Chapter membership is resolved through
``BibContent`` locus columns instead:

    Exercise.book_id == BibContent.bib_entry_id
    BibContent.chapter_number == <requested chapter>
    BibContent.first_exercise <= <exercise numeric suffix> <= BibContent.last_exercise

The exercise's numeric suffix is parsed from its ``exercise_id`` (e.g.
``phys-gauss-005`` -> ``5``) — no existing helper did this (verified gap,
see tasks/plans/2026-07-03-freeze-window-features-plan.md Phase 2b anchor).

Exercises that cannot be resolved to a chapter (no ``book_id``, no matching
``BibContent`` row for the requested chapter, unparsable/out-of-range
suffix) are excluded silently from ``matched`` — this is reported as a
count, not an error (mirrors Bundle A/B's warn-not-fail precedent).

Overlapping ``BibContent`` ranges for the same book+chapter (a data-entry
error) are resolved by taking the first match (ordered by ``content_id``)
and recording a warning — never an arbitrary silent pick (locked decision,
plan's "Resolved design rules").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import BibContent
from workflow.db.models.exercises import Exercise

_SUFFIX_RE = re.compile(r"(\d+)$")


def parse_exercise_number(exercise_id: str) -> int | None:
    """Extract the trailing numeric suffix from an exercise_id.

    ``"phys-gauss-005"`` -> ``5``. Returns ``None`` if there is no trailing
    run of digits (e.g. an exercise_id with no numeric suffix at all).
    """
    match = _SUFFIX_RE.search(exercise_id)
    if match is None:
        return None
    return int(match.group(1))


@dataclass(frozen=True)
class ChapterFilterResult:
    """Result of filtering an exercise list down to a single chapter."""

    matched: tuple[Exercise, ...]
    excluded: int
    warnings: tuple[str, ...]


def _resolve_chapter_ranges(
    session: Session, book_ids: set[int], chapter: int
) -> tuple[dict[int, BibContent], list[str]]:
    """Return {bib_entry_id: chosen BibContent row} for the requested chapter.

    When a book has more than one ``BibContent`` row for the same chapter
    (overlapping-range data-entry error), the first row (ordered by
    ``content_id``) is chosen and a warning is appended.
    """
    if not book_ids:
        return {}, []

    rows = list(
        session.scalars(
            select(BibContent)
            .where(BibContent.bib_entry_id.in_(book_ids))
            .where(BibContent.chapter_number == chapter)
            .order_by(BibContent.bib_entry_id, BibContent.content_id)
        ).all()
    )

    by_book: dict[int, list[BibContent]] = {}
    for row in rows:
        by_book.setdefault(row.bib_entry_id, []).append(row)

    ranges: dict[int, BibContent] = {}
    warnings: list[str] = []
    for book_id, book_rows in by_book.items():
        if len(book_rows) > 1:
            warnings.append(
                f"book_id={book_id}: {len(book_rows)} overlapping BibContent "
                f"rows found for chapter {chapter}; using first match "
                f"(content_id={book_rows[0].content_id})."
            )
        ranges[book_id] = book_rows[0]
    return ranges, warnings


def filter_by_chapter(
    exercises: list[Exercise],
    chapter: int,
    session: Session,
) -> ChapterFilterResult:
    """Filter ``exercises`` down to those whose reference falls in ``chapter``.

    Exercises with no resolvable chapter are dropped and counted in
    ``excluded`` (not an error). See module docstring for the join/parse
    strategy and the overlapping-range fallback rule.
    """
    book_ids = {ex.book_id for ex in exercises if ex.book_id is not None}
    ranges, warnings = _resolve_chapter_ranges(session, book_ids, chapter)

    matched: list[Exercise] = []
    excluded = 0
    for ex in exercises:
        row = ranges.get(ex.book_id) if ex.book_id is not None else None
        if row is None or row.first_exercise is None or row.last_exercise is None:
            excluded += 1
            continue
        number = parse_exercise_number(ex.exercise_id)
        if number is None or not (row.first_exercise <= number <= row.last_exercise):
            excluded += 1
            continue
        matched.append(ex)

    return ChapterFilterResult(
        matched=tuple(matched), excluded=excluded, warnings=tuple(warnings)
    )
