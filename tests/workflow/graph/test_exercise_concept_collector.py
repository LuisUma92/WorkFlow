"""Tests for collect_exercise_concepts — exercise→concept GraphEdges in the knowledge graph."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from workflow.db.models.knowledge import DisciplineArea, MainTopic, Topic, Content, Concept
from workflow.db.models.exercises import Exercise, ExerciseConcept
from workflow.graph.collectors import build_knowledge_graph, collect_exercise_concepts
from workflow.graph.domain import GraphEdge, GraphNode


# ---------------------------------------------------------------------------
# Helpers — mirrors _seed_concept_chain pattern from Phase 3 tests
# ---------------------------------------------------------------------------

_counter = 0


def _seed_concept_chain(
    session: Session, name: str = "Physics", code_prefix: str = "phys"
) -> tuple[MainTopic, Content]:
    """Create DisciplineArea→MainTopic→Topic→Content chain, return (MainTopic, Content)."""
    global _counter
    _counter += 1
    suffix = _counter
    da = DisciplineArea(
        code=f"EC{suffix:04d}",
        name=name,
        discipline_num=suffix,
        topic_num=suffix,
        area_initials="EC",
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code=f"EM{suffix:04d}", name=name, discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    tp = Topic(discipline_area_id=da.id, name=f"{name} subtopic", serial_number=1)
    session.add(tp)
    session.flush()
    ct = Content(topic_id=tp.id, name=f"{name} content")
    session.add(ct)
    session.flush()
    return mt, ct


def _concept(session: Session, content: Content, code: str) -> Concept:
    c = Concept(content_id=content.id, domain="Información", code=code, label=code)
    session.add(c)
    session.flush()
    return c


def _exercise(session: Session, ex_id: str) -> Exercise:
    ex = Exercise(
        exercise_id=ex_id,
        source_path=f"/path/{ex_id}.tex",
        file_hash=f"hash-{ex_id}",
    )
    session.add(ex)
    session.flush()
    return ex


def _link(session: Session, exercise: Exercise, concept: Concept) -> ExerciseConcept:
    ec = ExerciseConcept(exercise_id=exercise.id, concept_id=concept.id)
    session.add(ec)
    session.flush()
    return ec


# ---------------------------------------------------------------------------
# collect_exercise_concepts unit tests
# ---------------------------------------------------------------------------


def test_collect_exercise_concepts_empty(global_session):
    """Empty DB → empty nodes and edges."""
    nodes, edges = collect_exercise_concepts(global_session)
    assert nodes == ()
    assert edges == ()


def test_collect_exercise_concepts_single_link(global_session):
    """One ExerciseConcept → one exercise node + one concept node + one edge."""
    _mt, ct = _seed_concept_chain(global_session, "Mechanics", "mech")
    concept = _concept(global_session, ct, "newton-law-ec")
    ex = _exercise(global_session, "ec-test-001")
    _link(global_session, ex, concept)

    nodes, edges = collect_exercise_concepts(global_session)

    node_ids = {n.node_id for n in nodes}
    assert f"exercise:{ex.exercise_id}" in node_ids
    assert f"concept:{concept.id}" in node_ids

    ex_node = next(n for n in nodes if n.node_id == f"exercise:{ex.exercise_id}")
    assert ex_node.node_type == "exercise"
    assert ex_node.label == ex.exercise_id

    cn_node = next(n for n in nodes if n.node_id == f"concept:{concept.id}")
    assert cn_node.node_type == "concept"
    assert cn_node.label == concept.code

    assert len(edges) == 1
    ge = edges[0]
    assert isinstance(ge, GraphEdge)
    assert ge.source_id == f"exercise:{ex.exercise_id}"
    assert ge.target_id == f"concept:{concept.id}"
    assert ge.edge_type == "exercise→concept"
    assert ge.label == concept.code


def test_collect_exercise_concepts_two_exercises(global_session):
    """Two ExerciseConcept rows → one concept node per unique concept + two edges."""
    _mt, ct = _seed_concept_chain(global_session, "Waves", "wave")
    concept = _concept(global_session, ct, "wave-motion-ec")
    ex1 = _exercise(global_session, "ec-wave-001")
    ex2 = _exercise(global_session, "ec-wave-002")
    _link(global_session, ex1, concept)
    _link(global_session, ex2, concept)

    nodes, edges = collect_exercise_concepts(global_session)

    # Concept node deduplicated
    concept_nodes = [n for n in nodes if n.node_id == f"concept:{concept.id}"]
    assert len(concept_nodes) == 1

    assert len(edges) == 2
    sources = {e.source_id for e in edges}
    assert f"exercise:{ex1.exercise_id}" in sources
    assert f"exercise:{ex2.exercise_id}" in sources


def test_collect_exercise_concepts_edge_type(global_session):
    """All edges have edge_type 'exercise→concept'."""
    _mt, ct = _seed_concept_chain(global_session, "Optics", "opt")
    c = _concept(global_session, ct, "refraction-ec")
    ex = _exercise(global_session, "ec-opt-001")
    _link(global_session, ex, c)

    _, edges = collect_exercise_concepts(global_session)

    assert all(e.edge_type == "exercise→concept" for e in edges)


# ---------------------------------------------------------------------------
# Integration: build_knowledge_graph includes exercise→concept edges
# ---------------------------------------------------------------------------


def test_build_knowledge_graph_includes_exercise_concepts(global_session):
    """build_knowledge_graph merges exercise→concept nodes and edges."""
    _mt, ct = _seed_concept_chain(global_session, "Thermodynamics", "thermo")
    concept = _concept(global_session, ct, "entropy-ec")
    ex = _exercise(global_session, "ec-thermo-001")
    _link(global_session, ex, concept)

    kg = build_knowledge_graph(global_session)

    ex_concept_edges = [e for e in kg.edges if e.edge_type == "exercise→concept"]
    assert len(ex_concept_edges) == 1
    assert ex_concept_edges[0].source_id == f"exercise:{ex.exercise_id}"
    assert ex_concept_edges[0].target_id == f"concept:{concept.id}"

    node_ids = {n.node_id for n in kg.nodes}
    assert f"concept:{concept.id}" in node_ids
    assert f"exercise:{ex.exercise_id}" in node_ids


def test_build_knowledge_graph_no_exercise_concepts_still_works(global_session):
    """Graph builds without error when there are no ExerciseConcept rows."""
    kg = build_knowledge_graph(global_session)
    assert kg is not None
    assert not any(e.edge_type == "exercise→concept" for e in kg.edges)
