"""Query helpers for NoteEdge (ITEP-0013 P2.3)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge

__all__ = ["list_edges", "get_edge"]


def list_edges(
    session: Session,
    *,
    source_zettel_id: str | None = None,
    edge_class: str | None = None,
    relation_type: str | None = None,
) -> list[tuple[NoteEdge, str | None]]:
    """Return (NoteEdge, source_zettel_id) pairs matching the given filters.

    source_zettel_id in the tuple is None when the Note row lacks a zettel_id.
    """
    stmt = (
        select(NoteEdge, Note.zettel_id)
        .join(Note, NoteEdge.source_id == Note.id)
    )
    if source_zettel_id is not None:
        stmt = stmt.where(Note.zettel_id == source_zettel_id)
    if edge_class is not None:
        stmt = stmt.where(NoteEdge.edge_class == edge_class)
    if relation_type is not None:
        stmt = stmt.where(NoteEdge.relation_type == relation_type)
    return list(session.execute(stmt).all())


def get_edge(session: Session, edge_id: int) -> NoteEdge | None:
    """Return a single NoteEdge by primary key, or None."""
    return session.get(NoteEdge, edge_id)
