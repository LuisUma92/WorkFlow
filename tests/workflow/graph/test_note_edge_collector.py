"""Tests for P2.6 — NoteEdge data in graph export.

RED phase: fail until collect_note_edges is added to collectors.py.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge
from workflow.graph.collectors import build_knowledge_graph, collect_note_edges
from workflow.graph.domain import GraphEdge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _note(session: Session, zettel_id: str) -> Note:
    n = Note(filename=f"{zettel_id}.md", reference=zettel_id, zettel_id=zettel_id)
    session.add(n)
    session.flush()
    return n


def _edge(
    session: Session,
    src: Note,
    tgt: Note | None,
    tgt_zettel_id: str,
    edge_class: str = "structural",
    relation_type: str = "continuation",
) -> NoteEdge:
    e = NoteEdge(
        source_id=src.id,
        target_id=tgt.id if tgt else None,
        target_zettel_id=tgt_zettel_id,
        edge_class=edge_class,
        relation_type=relation_type,
    )
    session.add(e)
    session.flush()
    return e


# ---------------------------------------------------------------------------
# collect_note_edges unit tests
# ---------------------------------------------------------------------------


def test_collect_note_edges_empty(global_session):
    nodes, edges = collect_note_edges(global_session)
    assert nodes == ()
    assert edges == ()


def test_collect_note_edges_resolved_structural(global_session):
    """Resolved structural edge appears as GraphEdge with correct fields."""
    src = _note(global_session, "graphsrc0000000")
    tgt = _note(global_session, "graphtgt0000000")
    _edge(global_session, src, tgt, tgt.zettel_id, "structural", "refines")

    nodes, edges = collect_note_edges(global_session)

    assert nodes == ()  # collect_note_edges adds no new nodes
    assert len(edges) == 1
    ge = edges[0]
    assert isinstance(ge, GraphEdge)
    assert ge.source_id == f"note:{src.id}"
    assert ge.target_id == f"note:{tgt.id}"
    assert ge.edge_type == "note_edge:structural"
    assert ge.label == "refines"


def test_collect_note_edges_resolved_associative(global_session):
    """Resolved associative edge is also included."""
    src = _note(global_session, "graphassoc00000")
    tgt = _note(global_session, "graphassoctgt00")
    _edge(global_session, src, tgt, tgt.zettel_id, "associative", "see_also")

    _, edges = collect_note_edges(global_session)

    assert len(edges) == 1
    assert edges[0].edge_type == "note_edge:associative"
    assert edges[0].label == "see_also"


def test_collect_note_edges_unresolved_excluded(global_session):
    """Edges with target_id=None are excluded — target not yet in DB."""
    src = _note(global_session, "graphunres00000")
    _edge(global_session, src, None, "future-note-000")

    _, edges = collect_note_edges(global_session)

    assert edges == ()


def test_collect_note_edges_mixed(global_session):
    """Only resolved edges returned from a mixed set."""
    src = _note(global_session, "graphmix-src000")
    tgt = _note(global_session, "graphmix-tgt000")
    _edge(global_session, src, tgt, tgt.zettel_id, "structural", "continuation")
    _edge(global_session, src, None, "graphmix-unres0")  # unresolved

    _, edges = collect_note_edges(global_session)

    assert len(edges) == 1
    assert edges[0].source_id == f"note:{src.id}"
    assert edges[0].target_id == f"note:{tgt.id}"


def test_collect_note_edges_multiple(global_session):
    """Multiple resolved edges all returned."""
    a = _note(global_session, "graphmulti-a000")
    b = _note(global_session, "graphmulti-b000")
    c = _note(global_session, "graphmulti-c000")
    _edge(global_session, a, b, b.zettel_id, "structural", "continuation")
    _edge(global_session, b, c, c.zettel_id, "structural", "refines")
    _edge(global_session, a, c, c.zettel_id, "associative", "see_also")

    _, edges = collect_note_edges(global_session)

    assert len(edges) == 3
    edge_types = {e.edge_type for e in edges}
    assert "note_edge:structural" in edge_types
    assert "note_edge:associative" in edge_types


# ---------------------------------------------------------------------------
# Integration: build_knowledge_graph includes note edges
# ---------------------------------------------------------------------------


def test_build_knowledge_graph_includes_note_edges(global_session):
    """build_knowledge_graph merges note edges into the full graph."""
    src = _note(global_session, "graphbuild-src0")
    tgt = _note(global_session, "graphbuild-tgt0")
    _edge(global_session, src, tgt, tgt.zettel_id, "structural", "continuation")

    kg = build_knowledge_graph(global_session)

    note_edge_types = {e.edge_type for e in kg.edges if e.edge_type.startswith("note_edge")}
    assert "note_edge:structural" in note_edge_types


def test_build_knowledge_graph_no_note_edges_still_works(global_session):
    """Graph builds without error when there are no NoteEdges."""
    kg = build_knowledge_graph(global_session)
    assert kg is not None
    # No note_edge entries
    assert not any(e.edge_type.startswith("note_edge") for e in kg.edges)
