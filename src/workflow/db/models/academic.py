"""
Academic models for the WorkFlow global database.

Four layers:
  1. Reference data  — Institution, MainTopic
  2. Master entities — Topic, Content, BibContent
  3. Course templates — Course, CourseContent, EvaluationTemplate, Item,
                        EvaluationItem, CourseEvaluation
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
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

from typing import TYPE_CHECKING

from workflow.db.base import GlobalBase

if TYPE_CHECKING:
    from workflow.db.models.bibliography import BibEntry
    from workflow.db.models.project import (
        GeneralProject,
        GeneralProjectTopic,
        LectureInstance,
    )

# Taxonomy enum values (copied from itep.structure to avoid cross-dependency)
_TAXONOMY_LEVELS = (
    "Recordar",
    "Comprender",
    "Análisis",
    "Usar-Aplicar",
    "Usar-Evaluar",
    "Usar-Crear",
    "Metacognitivo",
    "Sistema interno",
)

_TAXONOMY_DOMAINS = (
    "Información",
    "Procedimiento Mental",
    "Procedimiento Psicomotor",
    "Metacognitivo",
)


# ── Layer 1: Reference data ────────────────────────────────────────────


class Institution(GlobalBase):
    __tablename__ = "institution"

    id: Mapped[int] = mapped_column(primary_key=True)
    short_name: Mapped[str] = mapped_column(String(10), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    cycle_weeks: Mapped[int] = mapped_column(Integer)
    cycle_name: Mapped[str] = mapped_column(String(30))
    moodle_url: Mapped[str] = mapped_column(String(200), default="")

    courses: Mapped[list["Course"]] = relationship(back_populates="institution")
    evaluation_templates: Mapped[list["EvaluationTemplate"]] = relationship(
        back_populates="institution"
    )

    def __repr__(self) -> str:
        return f"<Institution {self.short_name}>"


class MainTopic(GlobalBase):
    __tablename__ = "main_topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(10), unique=True)
    ddc_mds: Mapped[str] = mapped_column(String(20), default="")

    topics: Mapped[list["Topic"]] = relationship(back_populates="main_topic")
    general_project: Mapped["GeneralProject | None"] = relationship(
        back_populates="main_topic"
    )

    def __repr__(self) -> str:
        return f"<MainTopic {self.code} {self.name}>"


# ── Layer 2: Master entities ───────────────────────────────────────────


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
    chapter_number: Mapped[int] = mapped_column(Integer)
    section_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    first_page: Mapped[int] = mapped_column(Integer)
    last_page: Mapped[int] = mapped_column(Integer)
    first_exercise: Mapped[int | None] = mapped_column(Integer, default=None)
    last_exercise: Mapped[int | None] = mapped_column(Integer, default=None)

    topic: Mapped["Topic"] = relationship(back_populates="contents")
    bib_links: Mapped[list["BibContent"]] = relationship(back_populates="content")
    course_links: Mapped[list["CourseContent"]] = relationship(back_populates="content")


class BibContent(GlobalBase):
    """Links a bibliography entry to a content section (replaces BookContent)."""

    __tablename__ = "bib_content"

    bib_entry_id: Mapped[int] = mapped_column(
        ForeignKey("bib_entry.id"), primary_key=True
    )
    content_id: Mapped[int] = mapped_column(ForeignKey("content.id"), primary_key=True)

    bib_entry: Mapped["BibEntry"] = relationship(back_populates="content_links")
    content: Mapped["Content"] = relationship(back_populates="bib_links")


# ── Layer 3: Course templates ──────────────────────────────────────────


class Course(GlobalBase):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    lectures_per_week: Mapped[int] = mapped_column(Integer, default=3)
    hours_per_lecture: Mapped[int] = mapped_column(Integer, default=2)

    institution: Mapped["Institution"] = relationship(back_populates="courses")
    course_contents: Mapped[list["CourseContent"]] = relationship(
        back_populates="course"
    )
    course_evaluations: Mapped[list["CourseEvaluation"]] = relationship(
        back_populates="course"
    )
    lecture_instances: Mapped[list["LectureInstance"]] = relationship(
        back_populates="course"
    )

    def __repr__(self) -> str:
        return f"<Course {self.code} {self.name}>"


class CourseContent(GlobalBase):
    __tablename__ = "course_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    content_id: Mapped[int] = mapped_column(ForeignKey("content.id"))
    lecture_week: Mapped[int] = mapped_column(Integer)

    course: Mapped["Course"] = relationship(back_populates="course_contents")
    content: Mapped["Content"] = relationship(back_populates="course_links")


class EvaluationTemplate(GlobalBase):
    __tablename__ = "evaluation_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"))
    name: Mapped[str] = mapped_column(String(80))
    template_file: Mapped[str] = mapped_column(String(300), default="")

    institution: Mapped["Institution"] = relationship(
        back_populates="evaluation_templates"
    )
    evaluation_items: Mapped[list["EvaluationItem"]] = relationship(
        back_populates="evaluation"
    )
    course_evaluations: Mapped[list["CourseEvaluation"]] = relationship(
        back_populates="evaluation"
    )


class Item(GlobalBase):
    __tablename__ = "item"
    __table_args__ = (
        CheckConstraint(
            "taxonomy_level IN ({})".format(
                ", ".join(f"'{v}'" for v in _TAXONOMY_LEVELS)
            ),
            name="ck_taxonomy_level",
        ),
        CheckConstraint(
            "taxonomy_domain IN ({})".format(
                ", ".join(f"'{v}'" for v in _TAXONOMY_DOMAINS)
            ),
            name="ck_taxonomy_domain",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    template_file: Mapped[str] = mapped_column(String(300), default="")
    taxonomy_level: Mapped[str] = mapped_column(String(30))
    taxonomy_domain: Mapped[str] = mapped_column(String(40))

    evaluation_links: Mapped[list["EvaluationItem"]] = relationship(
        back_populates="item"
    )


class EvaluationItem(GlobalBase):
    __tablename__ = "evaluation_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluation_template.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    total_amount: Mapped[int] = mapped_column(Integer, default=1)
    points_per_item: Mapped[int] = mapped_column(Integer, default=1)

    evaluation: Mapped["EvaluationTemplate"] = relationship(
        back_populates="evaluation_items"
    )
    item: Mapped["Item"] = relationship(back_populates="evaluation_links")


class CourseEvaluation(GlobalBase):
    __tablename__ = "course_evaluation"
    __table_args__ = (
        CheckConstraint("percentage >= 0 AND percentage <= 1", name="ck_pct_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluation_template.id"))
    serial_number: Mapped[int] = mapped_column(Integer, default=1)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    evaluation_week: Mapped[int] = mapped_column(Integer, default=1)

    course: Mapped["Course"] = relationship(back_populates="course_evaluations")
    evaluation: Mapped["EvaluationTemplate"] = relationship(
        back_populates="course_evaluations"
    )
