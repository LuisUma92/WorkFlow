"""TDD tests for workflow.topic.service.get_topic_by_serial (followup #9).

The single-query lookup is shared by add_topic's duplicate guard AND the
bulk-import engine. Both must resolve through this one predicate.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from workflow.db.models.knowledge import DisciplineArea
from workflow.topic.service import add_topic, get_topic_by_serial


def _seed_da(session: Session, code: str = "FS01") -> DisciplineArea:
    area = DisciplineArea(
        code=code,
        name=f"Area {code}",
        discipline_num=1,
        topic_num=1,
        area_initials=code[:2],
    )
    session.add(area)
    session.commit()
    return area


def test_returns_none_when_absent(global_session):
    da = _seed_da(global_session)
    assert get_topic_by_serial(global_session, da.id, 1) is None


def test_returns_matching_topic(global_session):
    da = _seed_da(global_session)
    t = add_topic(
        global_session, discipline_area_code=da.code, name="Cinemática", serial_number=7
    )
    global_session.commit()
    found = get_topic_by_serial(global_session, da.id, 7)
    assert found is not None
    assert found.id == t.id


def test_scoped_to_discipline_area(global_session):
    da1 = _seed_da(global_session, "FS01")
    da2 = _seed_da(global_session, "FS02")
    add_topic(
        global_session, discipline_area_code=da1.code, name="A", serial_number=1
    )
    global_session.commit()
    # same serial, different area → no match
    assert get_topic_by_serial(global_session, da2.id, 1) is None
