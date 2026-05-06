"""
SQLAlchemy 2.0 models for per-project slipbox.db (GlobalBase).

Ported from src/latexzettel/infra/orm.py (Peewee) to SQLAlchemy Mapped[] style.

Models:
    Note, Citation, Label, Link, Tag, NoteTag
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workflow.db.base import GlobalBase


class Note(GlobalBase):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    reference: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    last_build_date_html: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    last_build_date_pdf: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    last_edit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Phase 7b — Zettelkasten extended fields (all nullable for backward compat)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # note_type values: "permanent" | "literature" | "fleeting"
    source_format: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # source_format values: "md" | "tex"
    zettel_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        comment="Stable Zettelkasten ID (e.g., 20260326-gauss-law)",
    )

    # Phase B — link note to a MainTopic via real FK (post-ITEP-0011 P1).
    main_topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("main_topic.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "note_type IN ('permanent', 'literature', 'fleeting') OR note_type IS NULL",
            name="ck_note_type_valid",
        ),
        CheckConstraint(
            "source_format IN ('md', 'tex') OR source_format IS NULL",
            name="ck_source_format_valid",
        ),
    )

    citations: Mapped[list[Citation]] = relationship(
        "Citation", back_populates="note", cascade="all, delete-orphan"
    )
    labels: Mapped[list[Label]] = relationship(
        "Label", back_populates="note", cascade="all, delete-orphan"
    )
    references: Mapped[list[Link]] = relationship(
        "Link",
        foreign_keys="Link.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="note_tag", back_populates="notes"
    )
    main_topic: Mapped["MainTopic | None"] = relationship(
        "MainTopic", foreign_keys=[main_topic_id]
    )

    def __repr__(self) -> str:
        return f"<Note id={self.id} filename={self.filename!r}>"


class Citation(GlobalBase):
    """Tracks which notes reference which bibliography keys."""

    __tablename__ = "citation"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), nullable=False
    )
    citationkey: Mapped[str] = mapped_column(String, nullable=False)

    note: Mapped[Note] = relationship("Note", back_populates="citations")

    def __repr__(self) -> str:
        return f"<Citation id={self.id} citationkey={self.citationkey!r}>"


class Label(GlobalBase):
    """An anchor label defined inside a note."""

    __tablename__ = "label"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False)

    note: Mapped[Note] = relationship("Note", back_populates="labels")
    referenced_by: Mapped[list[Link]] = relationship(
        "Link",
        foreign_keys="Link.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Label id={self.id} label={self.label!r}>"


class Link(GlobalBase):
    """
    Directed link between notes.
    source = the Note containing the reference.
    target = the Label being pointed to.
    """

    __tablename__ = "link"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("label.id", ondelete="CASCADE"), nullable=False
    )

    source: Mapped[Note] = relationship(
        "Note", foreign_keys=[source_id], back_populates="references"
    )
    target: Mapped[Label] = relationship(
        "Label", foreign_keys=[target_id], back_populates="referenced_by"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_link_source_target"),
    )

    def __repr__(self) -> str:
        return (
            f"<Link id={self.id} source_id={self.source_id} target_id={self.target_id}>"
        )


class Tag(GlobalBase):
    """A tag that can be attached to many notes."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    notes: Mapped[list[Note]] = relationship(
        "Note", secondary="note_tag", back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag id={self.id} name={self.name!r}>"


class NoteTag(GlobalBase):
    """M2M through table between Note and Tag."""

    __tablename__ = "note_tag"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True
    )


class Concept(GlobalBase):
    """A General Main Concept present in the note"""

    __tablename__ = "concept"
    id: Mapped[int] = mapped_column(primary_key=True)
    main_topic_id: Mapped[int] = mapped_column(
        ForeignKey("main_topic.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(
        String(32), unique=True
    )  # slug, e.g. "newton-2nd-law"
    label: Mapped[str] = mapped_column(String(255))  # display name
    description: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("concept.id", ondelete="SET NULL")
    )  # optional hierarchy
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    main_topic: Mapped["MainTopic"] = relationship(back_populates="concepts")
    parent: Mapped["Concept | None"] = relationship(remote_side="Concept.id")


class NoteConcept(GlobalBase):
    """M2M relation Note to Concept"""

    __tablename__ = "note_concept"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concept.id", ondelete="CASCADE"), primary_key=True
    )


__all__ = [
    "Note",
    "Citation",
    "Label",
    "Link",
    "Tag",
    "NoteTag",
    "Concept",
    "NoteConcept",
]
