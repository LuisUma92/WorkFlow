"""Shared DB upsert helpers for Note-layer Link/Label/Citation rows.

Extracted from workflow.lecture.linker so both notes.sync and lecture.linker
can share the same primitives without private-symbol cross-imports (ADR-0007).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session


def upsert_label(session: Session, note_id: int, label_name: str) -> bool:
    """Insert a Label if it does not already exist. Returns True if created."""
    from workflow.db.models.notes import Label

    existing = session.scalars(
        select(Label).where(Label.note_id == note_id, Label.label == label_name)
    ).first()
    if existing is None:
        session.add(Label(note_id=note_id, label=label_name))
        return True
    return False


def upsert_link(session: Session, source_id: int, target_label_id: int) -> bool:
    """Insert a Link if it does not already exist. Returns True if created."""
    from workflow.db.models.notes import Link

    existing = session.scalars(
        select(Link).where(
            Link.source_id == source_id, Link.target_id == target_label_id
        )
    ).first()
    if existing is None:
        session.add(Link(source_id=source_id, target_id=target_label_id))
        return True
    return False


def upsert_note_edge(
    session: Session,
    source_id: int,
    target_zettel_id: str,
    edge_class: str,
    relation_type: str,
    *,
    target_id: int | None = None,
    weight: float = 1.0,
    rationale: str | None = None,
) -> bool:
    """Insert-or-skip: add the NoteEdge only if (source_id, target_zettel_id,
    relation_type) does not yet exist.  Returns True if a new row was inserted,
    False if the edge already existed (weight/rationale NOT updated on re-scan —
    mirrors upsert_link semantics, intentional for Phase 2.1).
    """
    from workflow.db.models.notes import NoteEdge

    # Key matches uq_note_edge_src_tgt_rel (source_id, target_zettel_id, relation_type).
    # edge_class is intentionally excluded: structural/associative type sets are disjoint,
    # so relation_type alone is unambiguous.
    existing = session.scalars(
        select(NoteEdge).where(
            NoteEdge.source_id == source_id,
            NoteEdge.target_zettel_id == target_zettel_id,
            NoteEdge.relation_type == relation_type,
        )
    ).first()
    if existing is None:
        session.add(NoteEdge(
            source_id=source_id,
            target_id=target_id,
            target_zettel_id=target_zettel_id,
            edge_class=edge_class,
            relation_type=relation_type,
            weight=weight,
            rationale=rationale,
        ))
        return True
    return False


def upsert_citation(session: Session, note_id: int, citationkey: str) -> bool:
    """Insert a Citation if it does not already exist. Returns True if created."""
    from workflow.db.models.notes import Citation

    existing = session.scalars(
        select(Citation).where(
            Citation.note_id == note_id, Citation.citationkey == citationkey
        )
    ).first()
    if existing is None:
        session.add(Citation(note_id=note_id, citationkey=citationkey))
        return True
    return False
