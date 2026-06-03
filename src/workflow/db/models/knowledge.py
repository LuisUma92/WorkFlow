"""
Knowledge structure models for the WorkFlow global database.

Four layers:
  1. Reference data  — DisciplineArea, MainTopic
  2. Master entities — Topic, Content, Concept
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from workflow.db.base import GlobalBase

if TYPE_CHECKING:
    from workflow.db.models.academic import CourseContent
    from workflow.db.models.bibliography import BibContent
    from workflow.db.models.project import GeneralProject, GeneralProjectTopic

# Taxonomy domain enum values.
# Defined here (master-entity layer) so academic.py can import upward without
# creating a layer inversion (ADR ITEP-0002).
_TAXONOMY_DOMAINS = (
    "Información",
    "Procedimiento Mental",
    "Procedimiento Psicomotor",
    "Metacognitivo",
)


class DisciplineArea(GlobalBase):
    """Reference table for discipline area codes loaded from data/DD-*Codes.csv.

    Source of truth for valid DDTTAA codes (see ADR ITEP-0008). Distinct from
    MainTopic: DisciplineArea is pure reference data; MainTopic carries the
    project-hierarchy (parent_id → child) and is created on-demand by inittex.
    """

    __tablename__ = "discipline_area"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(6), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    dewey: Mapped[str] = mapped_column(String(20), default="")
    discipline_num: Mapped[int] = mapped_column(Integer)
    topic_num: Mapped[int] = mapped_column(Integer)
    area_initials: Mapped[str] = mapped_column(String(2))

    topics: Mapped[list["Topic"]] = relationship(back_populates="discipline_area")

    def __repr__(self) -> str:
        return f"<DisciplineArea {self.code} {self.name}>"


# ── Layer 2: Master entities ───────────────────────────────────────────
class MainTopic(GlobalBase):
    __tablename__ = "main_topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(10), unique=True)
    ddc_mds: Mapped[str] = mapped_column(String(20), default="")
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("main_topic.id"), nullable=True, default=None
    )
    discipline_area_id: Mapped[int] = mapped_column(
        ForeignKey("discipline_area.id"), nullable=False
    )

    syllabus_entries: Mapped[list["MainTopicSyllabus"]] = relationship(
        back_populates="main_topic", cascade="all, delete-orphan"
    )
    general_project: Mapped["GeneralProject | None"] = relationship(
        back_populates="main_topic"
    )
    parent: Mapped["MainTopic | None"] = relationship(
        back_populates="children",
        remote_side="MainTopic.id",
    )
    children: Mapped[list["MainTopic"]] = relationship(back_populates="parent")
    discipline_area: Mapped["DisciplineArea"] = relationship()

    def __repr__(self) -> str:
        return f"<MainTopic {self.code} {self.name}>"


class Topic(GlobalBase):
    __tablename__ = "topic"
    __table_args__ = (
        UniqueConstraint("discipline_area_id", "serial_number", name="uq_topic_da_serial"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    discipline_area_id: Mapped[int] = mapped_column(
        ForeignKey("discipline_area.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[int] = mapped_column(Integer)

    discipline_area: Mapped["DisciplineArea"] = relationship(back_populates="topics")
    syllabus_entries: Mapped[list["MainTopicSyllabus"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    contents: Mapped[list["Content"]] = relationship(back_populates="topic")
    general_project_links: Mapped[list["GeneralProjectTopic"]] = relationship(
        back_populates="topic"
    )

    def __repr__(self) -> str:
        return f"<Topic {self.serial_number}: {self.name}>"


class MainTopicSyllabus(GlobalBase):
    """Join table linking a MainTopic to a Topic with syllabus ordering metadata.

    Composite PK (main_topic_id, topic_id). Both FKs ON DELETE CASCADE so that
    removing either end automatically removes the syllabus entry.
    """

    __tablename__ = "main_topic_syllabus"

    main_topic_id: Mapped[int] = mapped_column(
        ForeignKey("main_topic.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"), primary_key=True
    )
    week_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)

    main_topic: Mapped["MainTopic"] = relationship(back_populates="syllabus_entries")
    topic: Mapped["Topic"] = relationship(back_populates="syllabus_entries")

    def __repr__(self) -> str:
        return f"<MainTopicSyllabus mt={self.main_topic_id} topic={self.topic_id} week={self.week_no}>"


class Content(GlobalBase):
    __tablename__ = "content"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id"))
    name: Mapped[str] = mapped_column(String(200))

    topic: Mapped["Topic"] = relationship(back_populates="contents")
    bib_links: Mapped[list["BibContent"]] = relationship(back_populates="content")
    course_links: Mapped[list["CourseContent"]] = relationship(back_populates="content")
    concepts: Mapped[list["Concept"]] = relationship(back_populates="content")


class Concept(GlobalBase):
    """A General Main Concept present in the note"""

    __tablename__ = "concept"
    __table_args__ = (
        CheckConstraint(
            "domain IN ({})".format(
                ", ".join(f"'{v}'" for v in _TAXONOMY_DOMAINS)
            ),
            name="ck_taxonomy_domain",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content.id", ondelete="RESTRICT"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(40))
    code: Mapped[str] = mapped_column(
        String(32), unique=True
    )  # slug, e.g. "newton-2nd-law"
    label: Mapped[str] = mapped_column(String(255))  # display name
    description: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("concept.id", ondelete="SET NULL")
    )  # optional hierarchy
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    content: Mapped["Content"] = relationship(back_populates="concepts")
    parent: Mapped["Concept | None"] = relationship(remote_side="Concept.id")

    @property
    def main_topic(self) -> "MainTopic | None":
        """Deprecated: always returns None after Phase 4B re-root.

        Topic is now rooted at DisciplineArea, not MainTopic.  The MainTopic
        for a concept is project-context-dependent and requires an explicit
        MainTopicSyllabus lookup.  This property is preserved for API stability
        but returns None unconditionally.

        Use ``concept.content.topic.discipline_area`` for the canonical chain.
        """
        return None
