"""ITEP-0011 P5 — Project-scoped LocalBase models.

ProjectNote  — an idea, hypothesis, or connection note tied to a project.
PrismaDecision — screening decision for a bibliography entry (bibkey ref).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workflow.db.base import LocalBase

__all__ = ["ProjectNote", "PrismaDecision"]

_NOTE_KINDS = ("idea", "hypothesis", "connection")
_DECISION_VALS = ("included", "excluded", "uncertain")


class ProjectNote(LocalBase):
    """An atomic knowledge fragment scoped to a project's local slipbox.

    ``global_note_ref`` is an optional zettel_id string pointing at a note in
    the unified vault (GlobalBase). No FK — cross-database references are not
    enforceable in SQLite.
    """

    __tablename__ = "project_note"
    __table_args__ = (
        CheckConstraint(f"kind IN {_NOTE_KINDS!r}", name="ck_project_note_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    global_note_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )


class PrismaDecision(LocalBase):
    """Screening decision for a PRISMA review article, scoped to a project.

    ``bibkey`` is a logical reference to ``BibEntry.bibkey`` in GlobalBase.
    No FK — cross-database references are not enforceable in SQLite.
    UNIQUE on ``bibkey`` so each article has exactly one decision per project.
    """

    __tablename__ = "prisma_decision"
    __table_args__ = (
        CheckConstraint(
            f"decision IN {_DECISION_VALS!r}", name="ck_prisma_decision_val"
        ),
        UniqueConstraint("bibkey", name="uq_prisma_decision_bibkey"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bibkey: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
