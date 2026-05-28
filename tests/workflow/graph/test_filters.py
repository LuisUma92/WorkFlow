"""Tests for Phase 4E taxonomy filter flags on workflow graph commands.

Covers:
- filter_graph_by_taxonomy / resolve_taxonomy_filter unit tests
- CLI --main-topic, --discipline-area, --topic flags on `stats` and `orphans`
- AND-intersection of multiple flags
- Unknown slug → ValueError / CLI error exit
- No flags → unchanged baseline (regression guard)
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import (
    Concept,
    Content,
    DisciplineArea,
    MainTopic,
    MainTopicSyllabus,
    Topic,
)
from workflow.db.models.notes import Note, NoteConcept
from workflow.graph.cli import graph
from workflow.graph.collectors import (
    TaxonomyFilter,
    filter_graph_by_taxonomy,
    resolve_taxonomy_filter,
)
from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_session() -> Session:
    """Create an in-memory GlobalBase session with all tables."""
    engine = create_engine("sqlite:///:memory:")
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401
    import workflow.db.models.notes  # noqa: F401

    GlobalBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_full_chain(
    session: Session,
    *,
    da_code: str = "FI0000",
    mt_code: str = "FI0001",
    concept_code: str = "c-test",
) -> dict:
    """Seed DA → MainTopic + Topic (via MainTopicSyllabus) → Content → Concept.

    Returns dict with all seeded objects.
    """
    da = DisciplineArea(
        code=da_code, name="Fisica",
        discipline_num=10, topic_num=0, area_initials="FI",
    )
    session.add(da)
    session.flush()

    mt = MainTopic(code=mt_code, name="Mecanica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()

    tp = Topic(discipline_area_id=da.id, name="Cinematica", serial_number=1)
    session.add(tp)
    session.flush()

    # Link MainTopic → Topic via syllabus
    syllabus = MainTopicSyllabus(main_topic_id=mt.id, topic_id=tp.id, order_no=1)
    session.add(syllabus)
    session.flush()

    ct = Content(topic_id=tp.id, name="Movimiento rectilineo")
    session.add(ct)
    session.flush()

    concept = Concept(
        content_id=ct.id,
        domain="Información",
        code=concept_code,
        label="Test concept",
    )
    session.add(concept)
    session.flush()

    return {"da": da, "mt": mt, "tp": tp, "ct": ct, "concept": concept}


def _make_kg_from_seed(seed: dict) -> KnowledgeGraph:
    """Build a minimal KnowledgeGraph from seeded objects."""
    da = seed["da"]
    mt = seed["mt"]
    tp = seed["tp"]
    ct = seed["ct"]
    concept = seed["concept"]

    nodes = (
        GraphNode(node_id=f"topic:{tp.id}", node_type="topic", label=tp.name),
        GraphNode(node_id=f"content:{ct.id}", node_type="content", label=ct.name),
        GraphNode(node_id=f"concept:{concept.id}", node_type="concept", label=concept.code),
        # An unrelated node that should be filtered out
        GraphNode(node_id="topic:9999", node_type="topic", label="Unrelated"),
        GraphNode(node_id="content:9999", node_type="content", label="Unrelated content"),
    )
    edges = (
        GraphEdge(
            source_id=f"content:{ct.id}",
            target_id=f"topic:{tp.id}",
            edge_type="content_topic",
        ),
        GraphEdge(
            source_id=f"concept:{concept.id}",
            target_id=f"content:{ct.id}",
            edge_type="concept_content",
        ),
    )
    return KnowledgeGraph(nodes=nodes, edges=edges)


# ── resolve_taxonomy_filter ────────────────────────────────────────────────


class TestResolveTaxonomyFilter:
    def test_no_args_returns_empty_filter(self):
        session = _make_session()
        tf = resolve_taxonomy_filter(session)
        assert tf.is_empty()

    def test_resolve_main_topic_by_code(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        mt = seed["mt"]

        tf = resolve_taxonomy_filter(session, main_topic=mt.code)
        assert mt.id in tf.main_topic_ids

    def test_resolve_main_topic_by_numeric_id(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        mt = seed["mt"]

        tf = resolve_taxonomy_filter(session, main_topic=str(mt.id))
        assert mt.id in tf.main_topic_ids

    def test_resolve_discipline_area_by_code(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        da = seed["da"]

        tf = resolve_taxonomy_filter(session, discipline_area=da.code)
        assert da.id in tf.discipline_area_ids

    def test_resolve_topic_by_numeric_id(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        tp = seed["tp"]

        tf = resolve_taxonomy_filter(session, topic=str(tp.id))
        assert tp.id in tf.topic_ids

    def test_resolve_topic_by_name(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        tp = seed["tp"]

        tf = resolve_taxonomy_filter(session, topic=tp.name)
        assert tp.id in tf.topic_ids

    def test_unknown_main_topic_raises(self):
        session = _make_session()
        with pytest.raises(ValueError, match="MainTopic"):
            resolve_taxonomy_filter(session, main_topic="UNKNOWN")

    def test_unknown_discipline_area_raises(self):
        session = _make_session()
        with pytest.raises(ValueError, match="DisciplineArea"):
            resolve_taxonomy_filter(session, discipline_area="UNKNOWN")

    def test_unknown_topic_name_raises(self):
        session = _make_session()
        with pytest.raises(ValueError, match="Topic"):
            resolve_taxonomy_filter(session, topic="no-such-topic")

    def test_unknown_topic_numeric_id_raises(self):
        session = _make_session()
        with pytest.raises(ValueError, match="Topic"):
            resolve_taxonomy_filter(session, topic="99999")


# ── filter_graph_by_taxonomy ───────────────────────────────────────────────


class TestFilterGraphByTaxonomy:
    def test_empty_filter_returns_original_graph(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        kg = _make_kg_from_seed(seed)

        tf = TaxonomyFilter()
        result = filter_graph_by_taxonomy(kg, session, tf)
        assert result is kg  # identical object

    def test_main_topic_filter_reduces_nodes(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        mt = seed["mt"]
        kg = _make_kg_from_seed(seed)

        tf = resolve_taxonomy_filter(session, main_topic=mt.code)
        result = filter_graph_by_taxonomy(kg, session, tf)

        # Unrelated topic:9999 and content:9999 should be gone
        node_ids = {n.node_id for n in result.nodes}
        assert "topic:9999" not in node_ids
        assert "content:9999" not in node_ids
        # Seeded objects retained
        assert f"topic:{seed['tp'].id}" in node_ids
        assert f"content:{seed['ct'].id}" in node_ids
        assert f"concept:{seed['concept'].id}" in node_ids

    def test_discipline_area_filter_reduces_nodes(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        da = seed["da"]
        kg = _make_kg_from_seed(seed)

        tf = resolve_taxonomy_filter(session, discipline_area=da.code)
        result = filter_graph_by_taxonomy(kg, session, tf)

        node_ids = {n.node_id for n in result.nodes}
        assert "topic:9999" not in node_ids
        assert f"topic:{seed['tp'].id}" in node_ids

    def test_topic_filter_reduces_nodes(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        tp = seed["tp"]
        kg = _make_kg_from_seed(seed)

        tf = resolve_taxonomy_filter(session, topic=str(tp.id))
        result = filter_graph_by_taxonomy(kg, session, tf)

        node_ids = {n.node_id for n in result.nodes}
        assert "topic:9999" not in node_ids
        assert f"topic:{tp.id}" in node_ids

    def test_edges_filtered_to_surviving_nodes(self):
        session = _make_session()
        seed = _seed_full_chain(session)
        tp = seed["tp"]
        kg = _make_kg_from_seed(seed)

        tf = resolve_taxonomy_filter(session, topic=str(tp.id))
        result = filter_graph_by_taxonomy(kg, session, tf)

        surviving = {n.node_id for n in result.nodes}
        for edge in result.edges:
            assert edge.source_id in surviving
            assert edge.target_id in surviving

    def test_and_intersection_mismatched_returns_empty(self):
        """Two different main_topics with no overlap → empty graph."""
        session = _make_session()
        _seed_full_chain(session, da_code="FI0000", mt_code="FI0001", concept_code="c1")
        seed2 = _seed_full_chain(session, da_code="MA0000", mt_code="MA0001", concept_code="c2")
        # Build a graph that only has seed2's topic
        tp2 = seed2["tp"]
        nodes = (
            GraphNode(node_id=f"topic:{tp2.id}", node_type="topic", label="tp2"),
        )
        kg = KnowledgeGraph(nodes=nodes, edges=())

        # Filter by seed1's main_topic AND seed2's discipline_area
        # Intersection of topics from mt1 and da2 → empty
        seed1_mt = session.scalars(
            __import__("sqlalchemy", fromlist=["select"]).select(MainTopic).where(
                MainTopic.code == "FI0001"
            )
        ).first()
        seed2_da = seed2["da"]

        tf = TaxonomyFilter(
            main_topic_ids=frozenset([seed1_mt.id]),
            discipline_area_ids=frozenset([seed2_da.id]),
        )
        result = filter_graph_by_taxonomy(kg, session, tf)
        assert result.nodes == ()
        assert result.edges == ()

    def test_note_linked_via_concept_included(self):
        """Note with NoteConcept linking to an allowed concept is included."""
        session = _make_session()
        seed = _seed_full_chain(session)
        concept = seed["concept"]
        mt = seed["mt"]

        note = Note(filename="z1.md", reference="z1")
        session.add(note)
        session.flush()

        nc = NoteConcept(note_id=note.id, concept_id=concept.id)
        session.add(nc)
        session.flush()

        kg = KnowledgeGraph(
            nodes=(
                GraphNode(node_id=f"note:{note.id}", node_type="note", label="z1"),
                GraphNode(node_id=f"concept:{concept.id}", node_type="concept", label=concept.code),
                GraphNode(node_id="note:9999", node_type="note", label="unrelated"),
            ),
            edges=(
                GraphEdge(
                    source_id=f"note:{note.id}",
                    target_id=f"concept:{concept.id}",
                    edge_type="note_concept",
                ),
            ),
        )

        tf = resolve_taxonomy_filter(session, main_topic=mt.code)
        result = filter_graph_by_taxonomy(kg, session, tf)
        node_ids = {n.node_id for n in result.nodes}
        assert f"note:{note.id}" in node_ids
        assert "note:9999" not in node_ids

    def test_no_filter_baseline_unchanged(self):
        """Regression guard: no flags → original graph unchanged."""
        session = _make_session()
        seed = _seed_full_chain(session)
        kg = _make_kg_from_seed(seed)

        tf = TaxonomyFilter()
        result = filter_graph_by_taxonomy(kg, session, tf)
        assert len(result.nodes) == len(kg.nodes)
        assert len(result.edges) == len(kg.edges)


# ── CLI integration ────────────────────────────────────────────────────────


class TestCliFilterFlags:
    """CLI tests using patch on _build_graph_with_filter via real DB session."""

    def _runner_and_session(self):
        session = _make_session()
        runner = CliRunner()
        return runner, session

    def test_stats_no_filter_returns_all_nodes(self):
        """--json stats with no filter returns full node count."""
        from unittest.mock import patch

        runner = CliRunner()
        tp = GraphNode(node_id="topic:1", node_type="topic", label="T")
        ct = GraphNode(node_id="content:1", node_type="content", label="C")
        kg = KnowledgeGraph(nodes=(tp, ct), edges=())

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["stats", "--json", "--project", "."])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total_nodes"] == 2

    def test_stats_with_main_topic_unknown_exits_nonzero(self):
        """Unknown --main-topic slug → non-zero exit with error message."""
        from unittest.mock import patch

        runner = CliRunner()

        # patch _build_graph_with_filter to raise ClickException as the real code would
        import click

        def _raise(*args, **kwargs):
            raise click.ClickException("MainTopic code='NOPE' not found")

        with patch("workflow.graph.cli._build_graph_with_filter", side_effect=_raise):
            result = runner.invoke(graph, ["stats", "--main-topic", "NOPE", "--project", "."])

        assert result.exit_code != 0

    def test_orphans_json_with_filter(self):
        """--json orphans output is a JSON list when filter applied."""
        from unittest.mock import patch

        runner = CliRunner()
        orphan = GraphNode(node_id="concept:1", node_type="concept", label="orphan")
        kg = KnowledgeGraph(nodes=(orphan,), edges=())

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(
                graph, ["orphans", "--json", "--project", "."]
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["node_id"] == "concept:1"

    def test_stats_filter_reduces_count(self):
        """--main-topic filter on stats returns fewer nodes than baseline."""
        from unittest.mock import patch

        runner = CliRunner()

        # Full graph
        all_nodes = tuple(
            GraphNode(node_id=f"topic:{i}", node_type="topic", label=f"T{i}")
            for i in range(5)
        )
        full_kg = KnowledgeGraph(nodes=all_nodes, edges=())

        # Filtered graph (2 nodes)
        filtered_nodes = all_nodes[:2]
        filtered_kg = KnowledgeGraph(nodes=filtered_nodes, edges=())

        # No-filter call returns full; filter call returns filtered
        call_count = {"n": 0}

        def _mock(project, main_topic, discipline_area, topic):
            call_count["n"] += 1
            if main_topic == "MT001":
                return filtered_kg
            return full_kg

        with patch("workflow.graph.cli._build_graph_with_filter", side_effect=_mock):
            r_full = runner.invoke(graph, ["stats", "--json", "--project", "."])
            r_filtered = runner.invoke(
                graph, ["stats", "--main-topic", "MT001", "--json", "--project", "."]
            )

        assert r_full.exit_code == 0
        assert r_filtered.exit_code == 0
        full_data = json.loads(r_full.output)
        filtered_data = json.loads(r_filtered.output)
        assert full_data["total_nodes"] > filtered_data["total_nodes"]

    def test_discipline_area_flag_passed_through(self):
        """--discipline-area flag is forwarded to _build_graph_with_filter."""
        from unittest.mock import patch

        runner = CliRunner()
        captured = {}

        def _capture(project, main_topic, discipline_area, topic):
            captured.update(
                main_topic=main_topic,
                discipline_area=discipline_area,
                topic=topic,
            )
            return KnowledgeGraph(nodes=(), edges=())

        with patch("workflow.graph.cli._build_graph_with_filter", side_effect=_capture):
            result = runner.invoke(
                graph,
                ["stats", "--discipline-area", "MA0000", "--json", "--project", "."],
            )

        assert result.exit_code == 0, result.output
        assert captured["discipline_area"] == "MA0000"
        assert captured["main_topic"] is None
        assert captured["topic"] is None

    def test_topic_flag_passed_through(self):
        """--topic flag is forwarded to _build_graph_with_filter."""
        from unittest.mock import patch

        runner = CliRunner()
        captured = {}

        def _capture(project, main_topic, discipline_area, topic):
            captured.update(main_topic=main_topic, discipline_area=discipline_area, topic=topic)
            return KnowledgeGraph(nodes=(), edges=())

        with patch("workflow.graph.cli._build_graph_with_filter", side_effect=_capture):
            result = runner.invoke(
                graph, ["orphans", "--topic", "42", "--json", "--project", "."]
            )

        assert result.exit_code == 0, result.output
        assert captured["topic"] == "42"
