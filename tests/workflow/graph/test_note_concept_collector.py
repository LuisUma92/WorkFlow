"""Tests for collect_note_concepts — note→concept GraphEdges in the knowledge graph."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from workflow.db.models.academic import DisciplineArea, MainTopic
from workflow.db.models.notes import Concept, Note, NoteConcept
from workflow.graph.collectors import build_knowledge_graph, collect_note_concepts
from workflow.graph.domain import GraphEdge, GraphNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_topic_counter = 0


def _topic(session: Session, name: str = "Physics") -> MainTopic:
    global _topic_counter
    _topic_counter += 1
    suffix = _topic_counter
    da = DisciplineArea(
        code=f"SC{suffix:04d}",
        name=name,
        discipline_num=suffix,
        topic_num=suffix,
        area_initials="SC",
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code=f"MT{suffix:04d}", name=name, discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    return mt


def _concept(session: Session, topic: MainTopic, code: str, label: str = "") -> Concept:
    c = Concept(
        main_topic_id=topic.id,
        code=code,
        label=label or code,
    )
    session.add(c)
    session.flush()
    return c


def _note(session: Session, zettel_id: str) -> Note:
    n = Note(filename=f"{zettel_id}.md", reference=zettel_id, zettel_id=zettel_id)
    session.add(n)
    session.flush()
    return n


def _link(session: Session, note: Note, concept: Concept) -> NoteConcept:
    nc = NoteConcept(note_id=note.id, concept_id=concept.id)
    session.add(nc)
    session.flush()
    return nc


# ---------------------------------------------------------------------------
# collect_note_concepts unit tests
# ---------------------------------------------------------------------------


def test_collect_note_concepts_empty(global_session):
    nodes, edges = collect_note_concepts(global_session)
    assert nodes == ()
    assert edges == ()


def test_collect_note_concepts_single_link(global_session):
    """One NoteConcept → one concept node + one edge."""
    topic = _topic(global_session)
    concept = _concept(global_session, topic, "newton-2nd-law", "Newton's 2nd Law")
    note = _note(global_session, "nctest-src00000")
    _link(global_session, note, concept)

    nodes, edges = collect_note_concepts(global_session)

    assert len(nodes) == 1
    cn = nodes[0]
    assert isinstance(cn, GraphNode)
    assert cn.node_id == f"concept:{concept.id}"
    assert cn.node_type == "concept"
    assert cn.label == concept.code

    assert len(edges) == 1
    ge = edges[0]
    assert isinstance(ge, GraphEdge)
    assert ge.source_id == f"note:{note.id}"
    assert ge.target_id == f"concept:{concept.id}"
    assert ge.edge_type == "note_concept"
    assert ge.label == concept.code


def test_collect_note_concepts_shared_concept_deduplicated(global_session):
    """Two notes linked to same concept → one concept node, two edges."""
    topic = _topic(global_session, "Math")
    concept = _concept(global_session, topic, "calculus", "Calculus")
    note_a = _note(global_session, "ncshared-a00000")
    note_b = _note(global_session, "ncshared-b00000")
    _link(global_session, note_a, concept)
    _link(global_session, note_b, concept)

    nodes, edges = collect_note_concepts(global_session)

    concept_nodes = [n for n in nodes if n.node_id == f"concept:{concept.id}"]
    assert len(concept_nodes) == 1  # deduplicated

    assert len(edges) == 2
    sources = {e.source_id for e in edges}
    assert f"note:{note_a.id}" in sources
    assert f"note:{note_b.id}" in sources


def test_collect_note_concepts_multiple_concepts(global_session):
    """One note linked to two concepts → two nodes + two edges."""
    topic = _topic(global_session, "Biology")
    c1 = _concept(global_session, topic, "dna", "DNA")
    c2 = _concept(global_session, topic, "rna", "RNA")
    note = _note(global_session, "ncmulti-src0000")
    _link(global_session, note, c1)
    _link(global_session, note, c2)

    nodes, edges = collect_note_concepts(global_session)

    node_ids = {n.node_id for n in nodes}
    assert f"concept:{c1.id}" in node_ids
    assert f"concept:{c2.id}" in node_ids
    assert len(edges) == 2
    targets = {e.target_id for e in edges}
    assert f"concept:{c1.id}" in targets
    assert f"concept:{c2.id}" in targets


def test_collect_note_concepts_edge_type(global_session):
    """Edge type is always 'note_concept'."""
    topic = _topic(global_session, "Chemistry")
    concept = _concept(global_session, topic, "oxidation")
    note = _note(global_session, "nctype-src00000")
    _link(global_session, note, concept)

    _, edges = collect_note_concepts(global_session)

    assert all(e.edge_type == "note_concept" for e in edges)


# ---------------------------------------------------------------------------
# Integration: build_knowledge_graph includes concept nodes and edges
# ---------------------------------------------------------------------------


def test_build_knowledge_graph_includes_note_concepts(global_session):
    """build_knowledge_graph merges concept nodes and note_concept edges."""
    topic = _topic(global_session, "Physics")
    concept = _concept(global_session, topic, "gravity", "Gravity")
    note = _note(global_session, "ncbuild-src0000")
    _link(global_session, note, concept)

    kg = build_knowledge_graph(global_session)

    concept_node_ids = {n.node_id for n in kg.nodes if n.node_type == "concept"}
    assert f"concept:{concept.id}" in concept_node_ids

    note_concept_edges = [e for e in kg.edges if e.edge_type == "note_concept"]
    assert len(note_concept_edges) == 1
    assert note_concept_edges[0].source_id == f"note:{note.id}"
    assert note_concept_edges[0].target_id == f"concept:{concept.id}"


def test_build_knowledge_graph_no_note_concepts_still_works(global_session):
    """Graph builds without error when there are no NoteConcept rows."""
    kg = build_knowledge_graph(global_session)
    assert kg is not None
    assert not any(e.edge_type == "note_concept" for e in kg.edges)
