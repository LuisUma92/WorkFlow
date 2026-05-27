"""
Maturation signal evaluation (ADR ITEP-0009 Part II).

Computes the queryable subset of the Zettelkasten → ITeP maturation
criteria for an area-level :class:`MainTopic` (``parent_id IS NULL``).
Note-count / formal-product / PRISMA criteria require a slipbox.db scan
and are reported as ``met=None``: the caller (typically note-curator in
the 01-U workspace) supplies them.

The discipline-aware bib threshold per ADR Part II:

* ``DD < 4``    — bibliographic_accumulation requires ≥ 3 sources.
* ``DD >= 4``  — hobby disciplines require ≥ 5 sources.

Counting rules:

* ``MainTopic`` ids considered = the area itself + all its children
  (``parent_id == area_id``).
* Bibliographic sources are counted as **distinct** ``BibEntry.id`` values
  reachable via ``Topic → Content → BibContent → BibEntry``.
* Courses / lecture instances are likewise counted distinct.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workflow.db import taxonomy
from workflow.db.models.knowledge import Content, MainTopic, Topic
from workflow.db.models.bibliography import BibContent
from workflow.db.models.academic import (
    Course,
    CourseContent,
)
from workflow.db.models.project import LectureInstance


HOBBY_BIB_THRESHOLD = 5
DEFAULT_BIB_THRESHOLD = 3


@dataclass(frozen=True)
class MaturationSignal:
    criterion: str
    met: bool | None  # None = needs out-of-band data (slipbox scan, user input)
    evidence: str


def _topic_ids_for_area(session: Session, area_id: int) -> list[int]:
    """Return MainTopic ids covering the area and its direct children."""
    rows = (
        session.execute(
            select(MainTopic.id).where(
                (MainTopic.id == area_id) | (MainTopic.parent_id == area_id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def _bib_count(session: Session, main_topic_ids: list[int]) -> int:
    if not main_topic_ids:
        return 0
    stmt = (
        select(func.count(func.distinct(BibContent.bib_entry_id)))
        .select_from(BibContent)
        .join(Content, Content.id == BibContent.content_id)
        .join(Topic, Topic.id == Content.topic_id)
        .where(Topic.main_topic_id.in_(main_topic_ids))
    )
    return int(session.execute(stmt).scalar_one() or 0)


def _course_count(session: Session, main_topic_ids: list[int]) -> int:
    if not main_topic_ids:
        return 0
    stmt = (
        select(func.count(func.distinct(Course.id)))
        .select_from(Course)
        .join(CourseContent, CourseContent.course_id == Course.id)
        .join(Content, Content.id == CourseContent.content_id)
        .join(Topic, Topic.id == Content.topic_id)
        .where(Topic.main_topic_id.in_(main_topic_ids))
    )
    return int(session.execute(stmt).scalar_one() or 0)


def _lecture_instance_count(session: Session, main_topic_ids: list[int]) -> int:
    if not main_topic_ids:
        return 0
    stmt = (
        select(func.count(func.distinct(LectureInstance.id)))
        .select_from(LectureInstance)
        .join(Course, Course.id == LectureInstance.course_id)
        .join(CourseContent, CourseContent.course_id == Course.id)
        .join(Content, Content.id == CourseContent.content_id)
        .join(Topic, Topic.id == Content.topic_id)
        .where(Topic.main_topic_id.in_(main_topic_ids))
    )
    return int(session.execute(stmt).scalar_one() or 0)


def _discipline_from_area_code(code: str) -> int | None:
    if len(code) < 2 or not code[:2].isdigit():
        return None
    return int(code[:2])


def evaluate_area(
    session: Session,
    area_main_topic_id: int,
    *,
    hobby: bool | None = None,
) -> list[MaturationSignal]:
    """Return a list of queryable maturation signals for an area MainTopic.

    ``hobby`` defaults to ``DD >= HOBBY_DD_THRESHOLD`` derived from the
    area's code; pass an explicit value to override.
    """
    area = session.get(MainTopic, area_main_topic_id)
    if area is None:
        raise ValueError(f"MainTopic {area_main_topic_id} not found.")
    if area.parent_id is not None:
        raise ValueError(
            f"MainTopic {area_main_topic_id} is not an area "
            f"(parent_id={area.parent_id})."
        )

    if hobby is None:
        dd = _discipline_from_area_code(area.code)
        hobby = dd is not None and taxonomy.is_hobby(dd)
    bib_threshold = HOBBY_BIB_THRESHOLD if hobby else DEFAULT_BIB_THRESHOLD

    main_topic_ids = _topic_ids_for_area(session, area.id)
    bib_n = _bib_count(session, main_topic_ids)
    course_n = _course_count(session, main_topic_ids)
    lecture_n = _lecture_instance_count(session, main_topic_ids)

    signals: list[MaturationSignal] = [
        MaturationSignal(
            criterion="bibliographic_accumulation",
            met=bib_n >= bib_threshold,
            evidence=f"{bib_n} distinct BibEntry (threshold={bib_threshold})",
        ),
        MaturationSignal(
            criterion="institutional_affiliation",
            met=course_n > 0,
            evidence=f"{course_n} linked Course rows",
        ),
        MaturationSignal(
            criterion="multi_semester_continuity",
            met=lecture_n >= 2,
            evidence=f"{lecture_n} LectureInstance rows linked",
        ),
        MaturationSignal(
            criterion="formal_product",
            met=None,
            evidence="needs slipbox scan (out of scope for global DB query)",
        ),
        MaturationSignal(
            criterion="systematic_review",
            met=None,
            evidence="needs PRISMA project scan",
        ),
        MaturationSignal(
            criterion="collaborative_scope",
            met=None,
            evidence="needs git remote / collaborator scan",
        ),
    ]
    return signals


def is_mature(signals: list[MaturationSignal]) -> bool:
    """True iff at least one criterion is met (Part II 'at least one' rule)."""
    return any(s.met is True for s in signals)


def all_queryable_negative(signals: list[MaturationSignal]) -> bool:
    """True iff every queryable criterion explicitly failed (no None, no True)."""
    queryable = [s for s in signals if s.met is not None]
    return bool(queryable) and all(s.met is False for s in queryable)
