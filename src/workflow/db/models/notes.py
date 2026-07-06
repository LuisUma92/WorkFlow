"""
SQLAlchemy 2.0 models for the unified note layer in workflow.db (GlobalBase).

Ported from src/latexzettel/infra/orm.py (Peewee) to SQLAlchemy Mapped[] style.

Models:
    Note, Citation, Label, Link, Tag, NoteTag
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workflow.db.base import GlobalBase

if TYPE_CHECKING:
    from workflow.db.models.knowledge import MainTopic


# --- ITEP-0013 / ITEP-0015 note-edge vocabulary — SINGLE SOURCE OF TRUTH ----
# The NoteEdge CHECK constraints below, the relations-frontmatter parser
# (workflow.notes.edges) and the frontmatter validator
# (workflow.validation.schemas) all derive their allowed values from here.
# Do NOT re-declare these literals anywhere else (ADR ITEP-0013 MUST rule;
# cf. ADR-0017 stub-drift lesson).
_STRUCTURAL_RELATION_TYPES_ORDERED = (
    "continuation",
    "refines",
    "branches",
    "synthesis",
    "rebuttal",
)
_ASSOCIATIVE_RELATION_TYPES_ORDERED = (
    "supports",
    "contradicts",
    "expands",
    "see_also",
)
_EDGE_CLASSES_ORDERED = ("structural", "associative")

STRUCTURAL_RELATION_TYPES: frozenset[str] = frozenset(_STRUCTURAL_RELATION_TYPES_ORDERED)
ASSOCIATIVE_RELATION_TYPES: frozenset[str] = frozenset(_ASSOCIATIVE_RELATION_TYPES_ORDERED)
EDGE_CLASSES: frozenset[str] = frozenset(_EDGE_CLASSES_ORDERED)


def edge_class_for_relation_type(rel_type: str) -> str | None:
    """Return the edge class for a relation type, or ``None`` if unknown.

    Args:
        rel_type: A relation type string (e.g. ``"continuation"``).

    Returns:
        ``"structural"`` for structural relation types,
        ``"associative"`` for associative relation types,
        ``None`` for any other value.
    """
    if rel_type in STRUCTURAL_RELATION_TYPES:
        return "structural"
    if rel_type in ASSOCIATIVE_RELATION_TYPES:
        return "associative"
    return None


# ITEP-0015: zettel_id is a NanoID — URL-safe alphabet, 8–21 chars.
ZETTEL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,21}$")


def _sql_in(values: tuple[str, ...]) -> str:
    """Render an ordered tuple as a SQL ``IN`` value list (single-quoted)."""
    return ", ".join(f"'{v}'" for v in values)


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


class NoteConcept(GlobalBase):
    """M2M relation Note to Concept"""

    __tablename__ = "note_concept"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concept.id", ondelete="CASCADE"), primary_key=True
    )


class NoteEdge(GlobalBase):
    """Directed semantic edge between two notes (ITEP-0013).

    source_id → the note declaring the relation.
    target_zettel_id → stable string ref; target_id is nullable until resolved.
    """

    __tablename__ = "note_edge"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("note.id", ondelete="SET NULL"), nullable=True
    )
    target_zettel_id: Mapped[str] = mapped_column(String(21))
    edge_class: Mapped[str] = mapped_column(String(16))
    relation_type: Mapped[str] = mapped_column(String(24))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    rationale: Mapped[str | None] = mapped_column(Text)
    # Python-side default is authoritative: it guarantees a NOT-NULL value on
    # ORM inserts even against live tables created before server_default was
    # added to this model (drift found 2026-07-05 — see docs/ADR note below).
    # server_default kept too so raw-SQL/DDL-level inserts stay covered.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            f"edge_class IN ({_sql_in(_EDGE_CLASSES_ORDERED)})",
            name="ck_note_edge_class_valid",
        ),
        CheckConstraint(
            "relation_type IN ("
            + _sql_in(
                _STRUCTURAL_RELATION_TYPES_ORDERED
                + _ASSOCIATIVE_RELATION_TYPES_ORDERED
            )
            + ")",
            name="ck_note_edge_relation_type_valid",
        ),
        UniqueConstraint(
            "source_id",
            "target_zettel_id",
            "relation_type",
            name="uq_note_edge_src_tgt_rel",
        ),
        Index("ix_note_edge_source", "source_id", "edge_class", "relation_type"),
        Index("ix_note_edge_target", "target_id", "edge_class", "relation_type"),
        Index("ix_note_edge_unresolved", "target_zettel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NoteEdge id={self.id} {self.edge_class}/{self.relation_type} "
            f"src={self.source_id} tgt={self.target_zettel_id!r}>"
        )


__all__ = [
    "Note",
    "Citation",
    "Label",
    "Link",
    "Tag",
    "NoteTag",
    "NoteConcept",
    "NoteEdge",
    # vocabulary constants
    "STRUCTURAL_RELATION_TYPES",
    "ASSOCIATIVE_RELATION_TYPES",
    "EDGE_CLASSES",
    "ZETTEL_ID_RE",
    # ordered tuples (for deterministic JSON output)
    "_STRUCTURAL_RELATION_TYPES_ORDERED",
    "_ASSOCIATIVE_RELATION_TYPES_ORDERED",
    "_EDGE_CLASSES_ORDERED",
    # helpers
    "edge_class_for_relation_type",
]
