"""TDD tests for workflow.content.service.get_content_by_name (followup #9).

The single-query lookup is shared by add_content's duplicate guard AND the
bulk-import engine. Both must resolve through this one predicate.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from workflow.content.service import add_content, get_content_by_name
from workflow.db.models.knowledge import DisciplineArea, Topic


def _seed_topic(session: Session) -> Topic:
    area = DisciplineArea(
        code="FS01",
        name="Area FS01",
        discipline_num=1,
        topic_num=1,
        area_initials="FS",
    )
    session.add(area)
    session.flush()
    topic = Topic(discipline_area_id=area.id, name="Cinemática", serial_number=1)
    session.add(topic)
    session.commit()
    return topic


def test_returns_none_when_absent(global_session):
    topic = _seed_topic(global_session)
    assert get_content_by_name(global_session, topic.id, "Posición") is None


def test_returns_matching_content(global_session):
    topic = _seed_topic(global_session)
    c = add_content(global_session, topic_id=topic.id, name="Posición")
    global_session.commit()
    found = get_content_by_name(global_session, topic.id, "Posición")
    assert found is not None
    assert found.id == c.id


def test_scoped_to_topic(global_session):
    topic = _seed_topic(global_session)
    add_content(global_session, topic_id=topic.id, name="Posición")
    global_session.commit()
    # different topic id → no match
    assert get_content_by_name(global_session, topic.id + 999, "Posición") is None
