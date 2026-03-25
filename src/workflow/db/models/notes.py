"""
SQLAlchemy 2.0 models for per-project slipbox.db (LocalBase).

Ported from src/latexzettel/infra/orm.py (Peewee) to SQLAlchemy Mapped[] style.

Models:
    Note, Citation, Label, Link, Tag, NoteTag
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workflow.db.base import LocalBase


class Note(LocalBase):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    reference: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    last_build_date_html: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_build_date_pdf: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_edit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    citations: Mapped[list[Citation]] = relationship(
        "Citation", back_populates="note", cascade="all, delete-orphan"
    )
    labels: Mapped[list[Label]] = relationship(
        "Label", back_populates="note", cascade="all, delete-orphan"
    )
    references: Mapped[list[Link]] = relationship(
        "Link", foreign_keys="Link.source_id", back_populates="source", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary="note_tag", back_populates="notes"
    )

    def __repr__(self) -> str:
        return f"<Note id={self.id} filename={self.filename!r}>"


class Citation(LocalBase):
    """Tracks which notes reference which bibliography keys."""

    __tablename__ = "citation"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("note.id", ondelete="CASCADE"), nullable=False)
    citationkey: Mapped[str] = mapped_column(String, nullable=False)

    note: Mapped[Note] = relationship("Note", back_populates="citations")

    def __repr__(self) -> str:
        return f"<Citation id={self.id} citationkey={self.citationkey!r}>"


class Label(LocalBase):
    """An anchor label defined inside a note."""

    __tablename__ = "label"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("note.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)

    note: Mapped[Note] = relationship("Note", back_populates="labels")
    referenced_by: Mapped[list[Link]] = relationship(
        "Link", foreign_keys="Link.target_id", back_populates="target", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Label id={self.id} label={self.label!r}>"


class Link(LocalBase):
    """
    Directed link between notes.
    source = the Note containing the reference.
    target = the Label being pointed to.
    """

    __tablename__ = "link"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("note.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[int] = mapped_column(ForeignKey("label.id", ondelete="CASCADE"), nullable=False)

    source: Mapped[Note] = relationship(
        "Note", foreign_keys=[source_id], back_populates="references"
    )
    target: Mapped[Label] = relationship(
        "Label", foreign_keys=[target_id], back_populates="referenced_by"
    )

    __table_args__ = (UniqueConstraint("source_id", "target_id", name="uq_link_source_target"),)

    def __repr__(self) -> str:
        return f"<Link id={self.id} source_id={self.source_id} target_id={self.target_id}>"


class Tag(LocalBase):
    """A tag that can be attached to many notes."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    notes: Mapped[list[Note]] = relationship(
        "Note", secondary="note_tag", back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag id={self.id} name={self.name!r}>"


class NoteTag(LocalBase):
    """M2M through table between Note and Tag."""

    __tablename__ = "note_tag"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True
    )


__all__ = ["Note", "Citation", "Label", "Link", "Tag", "NoteTag"]
