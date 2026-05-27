"""
Academic models for the WorkFlow global database.

Four layers:
  1. Reference data  — Institution
  2. Master entities — BibContent
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
from workflow.db.models.knowledge import _TAXONOMY_DOMAINS  # noqa: F401 (re-exported)

if TYPE_CHECKING:
    from workflow.db.models.bibliography import BibEntry
    from workflow.db.models.knowledge import Concept
    from workflow.db.models.project import (
        GeneralProject,
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
    description: Mapped[str] = mapped_column(String(500), default="")

    institution: Mapped["Institution"] = relationship(
        back_populates="evaluation_templates"
    )
    evaluation_items: Mapped[list["EvaluationItem"]] = relationship(
        back_populates="evaluation"
    )
    course_evaluations: Mapped[list["CourseEvaluation"]] = relationship(
        back_populates="evaluation"
    )

    @property
    def total_points(self) -> int:
        return sum(ei.total_amount * ei.points_per_item for ei in self.evaluation_items)


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
    item_type: Mapped[str | None] = mapped_column(String(20), default=None)

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
