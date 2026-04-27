"""
Project instance models for the WorkFlow global database.

Layer 4: Project instances — LectureInstance, GeneralProject,
         GeneralProjectBib, GeneralProjectTopic
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
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

from typing import TYPE_CHECKING

from workflow.db.base import GlobalBase

if TYPE_CHECKING:
    from workflow.db.models.academic import Course, MainTopic, Topic
    from workflow.db.models.bibliography import BibEntry


class LectureInstance(GlobalBase):
    __tablename__ = "lecture_instance"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    year: Mapped[int] = mapped_column(Integer)
    cycle: Mapped[int] = mapped_column(Integer)
    first_monday: Mapped[date] = mapped_column(Date)
    abs_parent_dir: Mapped[str] = mapped_column(String(500))
    abs_src_dir: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_modification: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    course: Mapped["Course"] = relationship(back_populates="lecture_instances")

    @property
    def root_dir(self) -> str:
        return f"{self.course.institution.short_name}-{self.course.code}"

    def __repr__(self) -> str:
        return f"<LectureInstance {self.course.code} {self.year}-{self.cycle}>"


_GENERAL_PROJECT_STATUSES = ("active", "archived", "suspended", "completed")


class GeneralProject(GlobalBase):
    __tablename__ = "general_project"
    __table_args__ = (
        CheckConstraint(
            "status IN ({})".format(
                ", ".join(f"'{v}'" for v in _GENERAL_PROJECT_STATUSES)
            ),
            name="ck_general_project_status",
        ),
        CheckConstraint(
            "year_init >= 0 AND year_init <= 99",
            name="ck_general_project_year_init",
        ),
        UniqueConstraint(
            "main_topic_id",
            "year_init",
            "project_initials",
            name="uq_general_project_area_year_pp",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    main_topic_id: Mapped[int] = mapped_column(ForeignKey("main_topic.id"), unique=True)
    abs_parent_dir: Mapped[str] = mapped_column(String(500))
    abs_src_dir: Mapped[str] = mapped_column(String(500))
    year_init: Mapped[int] = mapped_column(Integer, default=0)
    project_initials: Mapped[str] = mapped_column(String(2), default="")
    title: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    archived_at: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_modification: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    main_topic: Mapped["MainTopic"] = relationship(back_populates="general_project")
    bib_links: Mapped[list["GeneralProjectBib"]] = relationship(
        back_populates="general_project",
        cascade="all, delete-orphan",
    )
    topic_links: Mapped[list["GeneralProjectTopic"]] = relationship(
        back_populates="general_project",
        cascade="all, delete-orphan",
    )

    @property
    def area(self) -> "MainTopic":
        """Return the area-level MainTopic (parent) or the node itself if no parent."""
        return self.main_topic.parent or self.main_topic

    @property
    def root_dir(self) -> str:
        if self.year_init or self.project_initials:
            return (
                f"{self.area.code}-"
                f"{self.year_init:02d}{self.project_initials}-"
                f"{self.title or self.main_topic.name}"
            )
        # Legacy fallback for pre-ITEP-0008 records (no YYPP yet assigned).
        return f"{self.main_topic.code}-{self.main_topic.name}"

    def __repr__(self) -> str:
        return f"<GeneralProject {self.main_topic.code}>"


class GeneralProjectBib(GlobalBase):
    """Links a bibliography entry to a general project (replaces GeneralProjectBook)."""

    __tablename__ = "general_project_bib"

    general_project_id: Mapped[int] = mapped_column(
        ForeignKey("general_project.id"), primary_key=True
    )
    bib_entry_id: Mapped[int] = mapped_column(
        ForeignKey("bib_entry.id"), primary_key=True
    )

    general_project: Mapped["GeneralProject"] = relationship(back_populates="bib_links")
    bib_entry: Mapped["BibEntry"] = relationship(back_populates="general_project_links")


class GeneralProjectTopic(GlobalBase):
    __tablename__ = "general_project_topic"

    general_project_id: Mapped[int] = mapped_column(
        ForeignKey("general_project.id"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id"), primary_key=True)

    general_project: Mapped["GeneralProject"] = relationship(
        back_populates="topic_links"
    )
    topic: Mapped["Topic"] = relationship(back_populates="general_project_links")
