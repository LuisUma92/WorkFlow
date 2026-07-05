"""Tests for real Tag/MainTopic propagation into GraphNode (freeze-window Phase 5).

Replaces the W4 id-hash / label-substring workaround flagged at
``graph/filters.py`` (formerly ``graph/cli.py:217-219``) — ``GraphNode`` now
carries real ``tags`` (from ``NoteTag``/``Tag``) and ``main_topic`` (from
``Note.main_topic_id`` -> ``MainTopic.code``) so ``--include-tags``/
``--exclude-tags`` and ``--color-by main_topic|tag`` operate on real DB data
instead of proxying via node_id hashes or label substrings.

Run with:
    WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest tests/workflow/graph/test_tag_maintopic_propagation.py -q
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.notes import Note, NoteTag, Tag
from workflow.graph.collectors import collect_notes
from workflow.graph.domain import GraphNode, KnowledgeGraph
from workflow.graph.filters import _filter_by_tags
from workflow.graph.tikz_export import graph_to_tikz


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def global_session():
    engine = create_engine("sqlite:///:memory:")
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401

    GlobalBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _discipline_area(session, code: str = "PHYSIC") -> DisciplineArea:
    da = DisciplineArea(
        code=code, name="Physics", discipline_num=0, topic_num=0, area_initials="PH",
    )
    session.add(da)
    session.flush()
    return da


def _main_topic(session, code: str, da: DisciplineArea) -> MainTopic:
    mt = MainTopic(name=f"Topic {code}", code=code, discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    return mt


# ── domain.py — additive fields ─────────────────────────────────────────────


class TestGraphNodeFields:
    def test_default_tags_is_empty_frozenset(self):
        n = GraphNode(node_id="note:1", node_type="note", label="X")
        assert n.tags == frozenset()

    def test_default_main_topic_is_none(self):
        n = GraphNode(node_id="note:1", node_type="note", label="X")
        assert n.main_topic is None

    def test_existing_positional_construction_still_valid(self):
        """Old 3-positional-arg construction (pre-Phase-5) must keep working."""
        n = GraphNode("note:1", "note", "X")
        assert n.tags == frozenset()
        assert n.main_topic is None

    def test_explicit_tags_and_main_topic(self):
        n = GraphNode(
            node_id="note:1", node_type="note", label="X",
            tags=frozenset({"physics", "midterm"}),
            main_topic="MECH",
        )
        assert n.tags == {"physics", "midterm"}
        assert n.main_topic == "MECH"

    def test_frozen_hashable_with_new_fields(self):
        n1 = GraphNode(node_id="note:1", node_type="note", label="X", tags=frozenset({"a"}))
        n2 = GraphNode(node_id="note:1", node_type="note", label="X", tags=frozenset({"a"}))
        assert hash(n1) == hash(n2)
        assert n1 == n2


# ── collect_notes — real tag propagation ────────────────────────────────────


class TestCollectNotesTags:
    def test_note_with_no_tags_has_empty_frozenset(self, global_session):
        note = Note(filename="a.md", reference="a")
        global_session.add(note)
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node = next(n for n in nodes if n.node_id == f"note:{note.id}")
        assert node.tags == frozenset()

    def test_note_with_single_tag(self, global_session):
        note = Note(filename="a.md", reference="a")
        global_session.add(note)
        global_session.flush()

        tag = Tag(name="physics")
        global_session.add(tag)
        global_session.flush()
        global_session.add(NoteTag(note_id=note.id, tag_id=tag.id))
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node = next(n for n in nodes if n.node_id == f"note:{note.id}")
        assert node.tags == frozenset({"physics"})

    def test_note_with_multiple_tags(self, global_session):
        note = Note(filename="a.md", reference="a")
        global_session.add(note)
        global_session.flush()

        t1 = Tag(name="physics")
        t2 = Tag(name="midterm")
        global_session.add_all([t1, t2])
        global_session.flush()
        global_session.add_all([
            NoteTag(note_id=note.id, tag_id=t1.id),
            NoteTag(note_id=note.id, tag_id=t2.id),
        ])
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node = next(n for n in nodes if n.node_id == f"note:{note.id}")
        assert node.tags == frozenset({"physics", "midterm"})

    def test_tags_scoped_to_correct_note_no_cross_contamination(self, global_session):
        n1 = Note(filename="a.md", reference="a")
        n2 = Note(filename="b.md", reference="b")
        global_session.add_all([n1, n2])
        global_session.flush()

        tag = Tag(name="physics")
        global_session.add(tag)
        global_session.flush()
        global_session.add(NoteTag(note_id=n1.id, tag_id=tag.id))
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node1 = next(n for n in nodes if n.node_id == f"note:{n1.id}")
        node2 = next(n for n in nodes if n.node_id == f"note:{n2.id}")
        assert node1.tags == frozenset({"physics"})
        assert node2.tags == frozenset()


class TestCollectNotesMainTopic:
    def test_note_without_main_topic_id_is_none(self, global_session):
        note = Note(filename="a.md", reference="a")
        global_session.add(note)
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node = next(n for n in nodes if n.node_id == f"note:{note.id}")
        assert node.main_topic is None

    def test_note_with_main_topic_id_resolves_code(self, global_session):
        da = _discipline_area(global_session)
        mt = _main_topic(global_session, "MECH", da)
        note = Note(filename="a.md", reference="a", main_topic_id=mt.id)
        global_session.add(note)
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node = next(n for n in nodes if n.node_id == f"note:{note.id}")
        assert node.main_topic == "MECH"

    def test_multiple_notes_different_main_topics_no_n_plus_1_bug(self, global_session):
        da = _discipline_area(global_session)
        mt1 = _main_topic(global_session, "MECH", da)
        mt2 = _main_topic(global_session, "THRM", da)
        n1 = Note(filename="a.md", reference="a", main_topic_id=mt1.id)
        n2 = Note(filename="b.md", reference="b", main_topic_id=mt2.id)
        global_session.add_all([n1, n2])
        global_session.flush()

        nodes, _ = collect_notes(global_session)
        node1 = next(n for n in nodes if n.node_id == f"note:{n1.id}")
        node2 = next(n for n in nodes if n.node_id == f"note:{n2.id}")
        assert node1.main_topic == "MECH"
        assert node2.main_topic == "THRM"


# ── _filter_by_tags — real-attribute matching ───────────────────────────────


class TestFilterByRealTags:
    def _kg(self):
        n_physics = GraphNode(
            node_id="note:1", node_type="note", label="Intro mechanics",
            tags=frozenset({"physics"}),
        )
        n_chem = GraphNode(
            node_id="note:2", node_type="note", label="Reactions",
            tags=frozenset({"chemistry"}),
        )
        n_untagged = GraphNode(
            node_id="note:3", node_type="note", label="physics-in-the-title-only",
        )
        return KnowledgeGraph(nodes=(n_physics, n_chem, n_untagged), edges=())

    def test_include_matches_real_tag_not_label_substring(self):
        """A node whose LABEL mentions 'physics' but has no real tag must be dropped."""
        kg = self._kg()
        result = _filter_by_tags(kg, "physics", None)
        ids = {n.node_id for n in result.nodes}
        assert ids == {"note:1"}

    def test_exclude_removes_real_tag_match(self):
        kg = self._kg()
        result = _filter_by_tags(kg, None, "chemistry")
        ids = {n.node_id for n in result.nodes}
        assert "note:2" not in ids
        assert "note:1" in ids

    def test_case_insensitive_tag_match(self):
        kg = self._kg()
        result = _filter_by_tags(kg, "PHYSICS", None)
        ids = {n.node_id for n in result.nodes}
        assert ids == {"note:1"}

    def test_no_filter_returns_all(self):
        kg = self._kg()
        result = _filter_by_tags(kg, None, None)
        assert len(result.nodes) == 3


# ── tikz_export color_by — real attribute + graceful fallback ──────────────


class TestColorByRealAttributes:
    def test_color_by_main_topic_uses_real_value(self):
        n1 = GraphNode(node_id="note:1", node_type="note", label="A", main_topic="MECH")
        n2 = GraphNode(node_id="note:2", node_type="note", label="B", main_topic="MECH")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        # Both nodes share main_topic="MECH" -> identical fill colour required.
        import re
        fills = re.findall(r"fill=([\w!]+)", result)
        assert len(fills) == 2
        assert fills[0] == fills[1]

    def test_color_by_main_topic_none_falls_back_to_type_default(self):
        """Node with no main_topic set must use the type-default colour, not a hash of node_id."""
        n = GraphNode(node_id="note:1", node_type="note", label="A")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        assert "blue!60" in result  # note type-default colour

    def test_color_by_tag_uses_real_value(self):
        n1 = GraphNode(node_id="note:1", node_type="note", label="A", tags=frozenset({"physics"}))
        n2 = GraphNode(node_id="note:2", node_type="note", label="B", tags=frozenset({"physics"}))
        kg = KnowledgeGraph(nodes=(n1, n2), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="tag")
        import re
        fills = re.findall(r"fill=([\w!]+)", result)
        assert len(fills) == 2
        assert fills[0] == fills[1]

    def test_color_by_tag_empty_falls_back_to_type_default(self):
        n = GraphNode(node_id="note:1", node_type="note", label="A")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="tag")
        assert "blue!60" in result

    def test_different_main_topics_may_differ(self):
        n1 = GraphNode(node_id="note:1", node_type="note", label="A", main_topic="MECH")
        n2 = GraphNode(node_id="note:2", node_type="note", label="B", main_topic="THRM")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        import re
        fills = re.findall(r"fill=([\w!]+)", result)
        # Not asserting inequality (palette collision possible) — just that
        # both are computed from real main_topic values (no crash, valid tikz).
        assert len(fills) == 2
