"""Target resolution pass for NoteEdge (ITEP-0013 P2.5).

Matches unresolved NoteEdge.target_zettel_id against Note.zettel_id
and fills in target_id where a match is found.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge

__all__ = ["ResolveReport", "resolve_edge_targets"]


@dataclass
class ResolveReport:
    resolved: int
    unresolved: int
    dry_run: bool = False


def resolve_edge_targets(session: Session, *, dry_run: bool = False) -> ResolveReport:
    """Fill target_id on every NoteEdge whose target_zettel_id exists in Note.

    Returns a ResolveReport with counts of resolved and still-unresolved edges.
    When dry_run=True, counts what would be resolved without mutating any row.
    """
    unresolved_edges: list[NoteEdge] = list(
        session.scalars(
            select(NoteEdge).where(NoteEdge.target_id.is_(None))
        ).all()
    )

    if not unresolved_edges:
        return ResolveReport(resolved=0, unresolved=0, dry_run=dry_run)

    # Batch lookup: one query for all needed zettel_ids
    wanted_ids = {e.target_zettel_id for e in unresolved_edges}
    note_map: dict[str, int] = {
        row.zettel_id: row.id
        for row in session.scalars(
            select(Note).where(Note.zettel_id.in_(wanted_ids))
        ).all()
        if row.zettel_id is not None
    }

    resolved = 0
    unresolved = 0
    for edge in unresolved_edges:
        note_id = note_map.get(edge.target_zettel_id)
        if note_id is not None:
            if not dry_run:
                edge.target_id = note_id
            resolved += 1
        else:
            unresolved += 1

    if not dry_run and resolved:
        try:
            session.flush()
        except SQLAlchemyError as exc:
            session.rollback()
            raise RuntimeError(
                f"Resolution flush failed after {resolved} candidate(s) — no rows written."
            ) from exc

    return ResolveReport(resolved=resolved, unresolved=unresolved, dry_run=dry_run)
