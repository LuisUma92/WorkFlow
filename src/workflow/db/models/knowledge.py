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
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from workflow.db.base import GlobalBase

if TYPE_CHECKING:
    from workflow.db.models.project import GeneralProject, GeneralProjectTopic

from workflow.db.models.academic import _TAXONOMY_DOMAINS


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

    topics: Mapped[list["Topic"]] = relationship(back_populates="main_topic")
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

    id: Mapped[int] = mapped_column(primary_key=True)
    main_topic_id: Mapped[int] = mapped_column(ForeignKey("main_topic.id"))
    name: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[int] = mapped_column(Integer)

    main_topic: Mapped["MainTopic"] = relationship(back_populates="topics")
    contents: Mapped[list["Content"]] = relationship(back_populates="topic")
    general_project_links: Mapped[list["GeneralProjectTopic"]] = relationship(
        back_populates="topic"
    )

    def __repr__(self) -> str:
        return f"<Topic {self.serial_number}: {self.name}>"


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
