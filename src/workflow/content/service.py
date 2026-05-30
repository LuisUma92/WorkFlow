"""Content service — add, list, get."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.knowledge import Content, Topic

__all__ = [
    "ContentServiceError",
    "TopicNotFound",
    "DuplicateContent",
    "ContentNotFound",
    "add_content",
    "list_contents",
    "get_content",
]


class ContentServiceError(Exception):
    pass


class TopicNotFound(ContentServiceError):
    pass


class DuplicateContent(ContentServiceError):
    pass


class ContentNotFound(ContentServiceError):
    pass


def add_content(
    session: Session,
    *,
    topic_id: int,
    name: str,
) -> Content:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise TopicNotFound(f"Topic id={topic_id} not found.")

    existing = session.scalars(
        select(Content).where(
            Content.topic_id == topic_id,
            Content.name == name,
        )
    ).first()
    if existing is not None:
        raise DuplicateContent(
            f"Content {name!r} already exists in topic id={topic_id}."
        )

    c = Content(topic_id=topic_id, name=name)
    session.add(c)
    return c


def list_contents(
    session: Session,
    *,
    topic_id: int | None = None,
) -> list[Content]:
    q = select(Content).order_by(Content.id)
    if topic_id is not None:
        q = q.where(Content.topic_id == topic_id)
    return list(session.scalars(q).all())


def get_content(session: Session, content_id: int) -> Content | None:
    return session.get(Content, content_id)
