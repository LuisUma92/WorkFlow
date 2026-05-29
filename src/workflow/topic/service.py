"""Topic service — add, list, get."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.knowledge import DisciplineArea, Topic

__all__ = [
    "TopicError",
    "DisciplineAreaNotFound",
    "DuplicateTopic",
    "add_topic",
    "list_topics",
    "get_topic",
]


class TopicError(Exception):
    pass


class DisciplineAreaNotFound(TopicError):
    pass


class DuplicateTopic(TopicError):
    pass


def add_topic(
    session: Session,
    *,
    discipline_area_code: str,
    name: str,
    serial_number: int,
) -> Topic:
    da = session.scalars(
        select(DisciplineArea).where(DisciplineArea.code == discipline_area_code)
    ).first()
    if da is None:
        raise DisciplineAreaNotFound(
            f"DisciplineArea code {discipline_area_code!r} not found."
        )

    existing = session.scalars(
        select(Topic).where(
            Topic.discipline_area_id == da.id,
            Topic.serial_number == serial_number,
        )
    ).first()
    if existing is not None:
        raise DuplicateTopic(
            f"Topic with serial_number={serial_number} already exists "
            f"in discipline area {discipline_area_code!r}."
        )

    t = Topic(discipline_area_id=da.id, name=name, serial_number=serial_number)
    session.add(t)
    return t


def list_topics(
    session: Session,
    *,
    discipline_area_code: str | None = None,
) -> list[Topic]:
    q = select(Topic).order_by(Topic.serial_number)
    if discipline_area_code is not None:
        da = session.scalars(
            select(DisciplineArea).where(DisciplineArea.code == discipline_area_code)
        ).first()
        if da is None:
            raise DisciplineAreaNotFound(
                f"DisciplineArea code {discipline_area_code!r} not found."
            )
        q = q.where(Topic.discipline_area_id == da.id)
    return list(session.scalars(q).all())


def get_topic(session: Session, topic_id: int) -> Topic | None:
    return session.get(Topic, topic_id)
