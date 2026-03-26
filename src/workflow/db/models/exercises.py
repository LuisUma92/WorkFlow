"""
Exercise models for the WorkFlow global database.

The `.tex` file is the truth source for exercise content (stem, solution,
options). The DB stores only metadata and file references for indexing
and querying. See ADR-0010.

Tables:
  - Exercise     — metadata index over exercise `.tex` files
  - ExerciseOption — per-option metadata (label, correctness, sort order)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from typing import TYPE_CHECKING

from workflow.db.base import GlobalBase

if TYPE_CHECKING:
    from workflow.db.models.academic import Content
    from workflow.db.models.bibliography import BibEntry


class Exercise(GlobalBase):
    """Metadata index for an exercise `.tex` file.

    Content (stem, solution, options text) is read from the `.tex` file
    at parse/export time — never stored in the DB.
    """

    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        comment="Unique ID from commented YAML (e.g. phys-gauss-001)",
    )
    source_path: Mapped[str] = mapped_column(
        Text,
        comment="Absolute path to .tex file in 00EE-ExamplesExercises",
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        comment="SHA-256 of .tex file content at last sync",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="placeholder",
        comment="File lifecycle: placeholder | in_progress | complete",
    )
    type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="multichoice | essay | shortanswer | numerical | truefalse",
    )
    difficulty: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="easy | medium | hard",
    )
    taxonomy_level: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Bloom taxonomy level (matches itep TaxonomyLevel)",
    )
    taxonomy_domain: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Bloom taxonomy domain (matches itep TaxonomyDomain)",
    )
    tags: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON list of tag strings",
    )
    concepts: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON list of note IDs",
    )
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("content.id"),
        nullable=True,
        comment="FK to book chapter/section this exercise tests",
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("bib_entry.id"),
        nullable=True,
        comment="FK to source textbook",
    )
    default_grade: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Point value from \\pts{n}",
    )
    penalty: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="Penalty fraction for wrong answers",
    )
    has_images: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True if parser detects image references",
    )
    image_refs: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON list of image paths found in .tex file",
    )
    diagram_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="TikZ asset ID from \\qdiagram{}",
    )
    option_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of \\qpart entries",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    # Relationships
    options: Mapped[list["ExerciseOption"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        order_by="ExerciseOption.sort_order",
    )
    content: Mapped["Content | None"] = relationship()
    book: Mapped["BibEntry | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Exercise {self.exercise_id} [{self.status}]>"


class ExerciseOption(GlobalBase):
    """Metadata for a single answer option within an exercise.

    Option text is read from the `.tex` file at parse/export time.
    """

    __tablename__ = "exercise_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercise.id", ondelete="CASCADE"),
    )
    label: Mapped[str] = mapped_column(
        String(5),
        comment="Option label: a, b, c, d...",
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True if \\rightoption precedes this option",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # Relationships
    exercise: Mapped["Exercise"] = relationship(back_populates="options")

    def __repr__(self) -> str:
        correct = "✓" if self.is_correct else " "
        return f"<ExerciseOption {self.label} [{correct}]>"


__all__ = [
    "Exercise",
    "ExerciseOption",
]
