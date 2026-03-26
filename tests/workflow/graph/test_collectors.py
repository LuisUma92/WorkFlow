"""Tests for workflow.graph.collectors — in-memory DB fixtures."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workflow.db.base import GlobalBase, LocalBase
from workflow.db.models.academic import BibContent, Content, Course, CourseContent, MainTopic, Topic, Institution
from workflow.db.models.bibliography import BibEntry
from workflow.db.models.exercises import Exercise
from workflow.db.models.notes import Citation, Label, Link, Note
from workflow.graph.collectors import (
    build_knowledge_graph,
    collect_academic,
    collect_bibliography,
    collect_exercises,
    collect_notes,
)
from workflow.graph.domain import KnowledgeGraph


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def global_session():
    engine = create_engine("sqlite:///:memory:")
    # Import all models so metadata is complete
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401
    GlobalBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def local_session():
    engine = create_engine("sqlite:///:memory:")
    import workflow.db.models.notes  # noqa: F401
    LocalBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ── collect_notes ──────────────────────────────────────────────────────────


def test_collect_notes_empty_db(local_session):
    nodes, edges = collect_notes(local_session)
    assert nodes == ()
    assert edges == ()


def test_collect_notes_returns_note_nodes(local_session):
    note = Note(filename="foo.md", reference="foo")
    local_session.add(note)
    local_session.flush()

    nodes, edges = collect_notes(local_session)
    node_ids = {n.node_id for n in nodes}
    assert f"note:{note.id}" in node_ids
    node = next(n for n in nodes if n.node_id == f"note:{note.id}")
    assert node.node_type == "note"
    assert node.label == "foo.md"


def test_collect_notes_with_link(local_session):
    note1 = Note(filename="a.md", reference="a")
    note2 = Note(filename="b.md", reference="b")
    local_session.add_all([note1, note2])
    local_session.flush()

    label = Label(note_id=note2.id, label="b-section")
    local_session.add(label)
    local_session.flush()

    link = Link(source_id=note1.id, target_id=label.id)
    local_session.add(link)
    local_session.flush()

    nodes, edges = collect_notes(local_session)
    node_ids = {n.node_id for n in nodes}
    assert f"note:{note1.id}" in node_ids
    assert f"note:{note2.id}" in node_ids

    link_edges = [e for e in edges if e.edge_type == "link"]
    assert len(link_edges) == 1
    assert link_edges[0].source_id == f"note:{note1.id}"
    assert link_edges[0].target_id == f"note:{note2.id}"


def test_collect_notes_with_citation(local_session):
    note = Note(filename="x.md", reference="x")
    local_session.add(note)
    local_session.flush()

    cit = Citation(note_id=note.id, citationkey="Smith2020")
    local_session.add(cit)
    local_session.flush()

    nodes, edges = collect_notes(local_session)
    cit_edges = [e for e in edges if e.edge_type == "citation"]
    assert len(cit_edges) == 1
    assert cit_edges[0].source_id == f"note:{note.id}"
    assert cit_edges[0].target_id == "bib:Smith2020"


# ── collect_exercises ──────────────────────────────────────────────────────


def test_collect_exercises_empty(global_session):
    nodes, edges = collect_exercises(global_session)
    assert nodes == ()
    assert edges == ()


def test_collect_exercises_basic(global_session):
    ex = Exercise(
        exercise_id="phys-001",
        source_path="/path/phys-001.tex",
        file_hash="abc123",
    )
    global_session.add(ex)
    global_session.flush()

    nodes, edges = collect_exercises(global_session)
    node_ids = {n.node_id for n in nodes}
    assert "exercise:phys-001" in node_ids
    node = next(n for n in nodes if n.node_id == "exercise:phys-001")
    assert node.node_type == "exercise"


def test_collect_exercises_with_content_edge(global_session):
    main_topic = MainTopic(name="Physics", code="PHY")
    global_session.add(main_topic)
    global_session.flush()

    topic = Topic(main_topic_id=main_topic.id, name="Mechanics", serial_number=1)
    global_session.add(topic)
    global_session.flush()

    content = Content(
        topic_id=topic.id,
        chapter_number=1, section_number=1,
        name="Newton Laws", first_page=1, last_page=10,
    )
    global_session.add(content)
    global_session.flush()

    ex = Exercise(
        exercise_id="phys-002",
        source_path="/path/phys-002.tex",
        file_hash="def456",
        content_id=content.id,
    )
    global_session.add(ex)
    global_session.flush()

    nodes, edges = collect_exercises(global_session)
    content_edges = [e for e in edges if e.edge_type == "exercise_content"]
    assert len(content_edges) == 1
    assert content_edges[0].source_id == "exercise:phys-002"
    assert content_edges[0].target_id == f"content:{content.id}"


def test_collect_exercises_with_book_edge(global_session):
    bib = BibEntry(title="Physics Textbook", year=2020)
    global_session.add(bib)
    global_session.flush()

    ex = Exercise(
        exercise_id="phys-003",
        source_path="/path/phys-003.tex",
        file_hash="ghi789",
        book_id=bib.id,
    )
    global_session.add(ex)
    global_session.flush()

    nodes, edges = collect_exercises(global_session)
    book_edges = [e for e in edges if e.edge_type == "exercise_book"]
    assert len(book_edges) == 1
    assert book_edges[0].source_id == "exercise:phys-003"
    assert book_edges[0].target_id == f"bib:{bib.id}"


# ── collect_academic ───────────────────────────────────────────────────────


def test_collect_academic_empty(global_session):
    nodes, edges = collect_academic(global_session)
    assert nodes == ()
    assert edges == ()


def test_collect_academic_content_topic(global_session):
    main_topic = MainTopic(name="Math", code="MTH")
    global_session.add(main_topic)
    global_session.flush()

    topic = Topic(main_topic_id=main_topic.id, name="Calculus", serial_number=1)
    global_session.add(topic)
    global_session.flush()

    content = Content(
        topic_id=topic.id,
        chapter_number=1, section_number=2,
        name="Derivatives", first_page=50, last_page=75,
    )
    global_session.add(content)
    global_session.flush()

    nodes, edges = collect_academic(global_session)
    node_ids = {n.node_id for n in nodes}
    assert f"content:{content.id}" in node_ids
    assert f"topic:{topic.id}" in node_ids

    content_node = next(n for n in nodes if n.node_id == f"content:{content.id}")
    assert content_node.node_type == "content"
    topic_node = next(n for n in nodes if n.node_id == f"topic:{topic.id}")
    assert topic_node.node_type == "topic"


def test_collect_academic_course_node(global_session):
    inst = Institution(short_name="UCR", full_name="University", cycle_weeks=16, cycle_name="Semester")
    global_session.add(inst)
    global_session.flush()

    course = Course(institution_id=inst.id, code="FI-1001", name="Physics I")
    global_session.add(course)
    global_session.flush()

    nodes, edges = collect_academic(global_session)
    node_ids = {n.node_id for n in nodes}
    assert f"course:{course.id}" in node_ids
    course_node = next(n for n in nodes if n.node_id == f"course:{course.id}")
    assert course_node.node_type == "course"


def test_collect_academic_bib_content_edge(global_session):
    bib = BibEntry(title="Calculus Book", year=2019)
    global_session.add(bib)
    global_session.flush()

    main_topic = MainTopic(name="Math", code="MTH2")
    global_session.add(main_topic)
    global_session.flush()

    topic = Topic(main_topic_id=main_topic.id, name="Calculus", serial_number=1)
    global_session.add(topic)
    global_session.flush()

    content = Content(
        topic_id=topic.id,
        chapter_number=2, section_number=1,
        name="Integration", first_page=80, last_page=110,
    )
    global_session.add(content)
    global_session.flush()

    bc = BibContent(bib_entry_id=bib.id, content_id=content.id)
    global_session.add(bc)
    global_session.flush()

    nodes, edges = collect_academic(global_session)
    bib_content_edges = [e for e in edges if e.edge_type == "bib_content"]
    assert len(bib_content_edges) == 1
    assert bib_content_edges[0].source_id == f"bib:{bib.id}"
    assert bib_content_edges[0].target_id == f"content:{content.id}"


def test_collect_academic_course_content_edge(global_session):
    inst = Institution(short_name="UFi", full_name="UFide", cycle_weeks=16, cycle_name="Semester")
    global_session.add(inst)
    global_session.flush()

    course = Course(institution_id=inst.id, code="FI-2001", name="Physics II")
    global_session.add(course)
    global_session.flush()

    main_topic = MainTopic(name="Electro", code="ELE")
    global_session.add(main_topic)
    global_session.flush()

    topic = Topic(main_topic_id=main_topic.id, name="Electricity", serial_number=1)
    global_session.add(topic)
    global_session.flush()

    content = Content(
        topic_id=topic.id,
        chapter_number=20, section_number=1,
        name="Coulomb", first_page=400, last_page=420,
    )
    global_session.add(content)
    global_session.flush()

    cc = CourseContent(course_id=course.id, content_id=content.id, lecture_week=3)
    global_session.add(cc)
    global_session.flush()

    nodes, edges = collect_academic(global_session)
    cc_edges = [e for e in edges if e.edge_type == "course_content"]
    assert len(cc_edges) == 1
    assert cc_edges[0].source_id == f"course:{course.id}"
    assert cc_edges[0].target_id == f"content:{content.id}"


# ── collect_bibliography ───────────────────────────────────────────────────


def test_collect_bibliography_empty(global_session):
    nodes, edges = collect_bibliography(global_session)
    assert nodes == ()
    assert edges == ()


def test_collect_bibliography_returns_nodes(global_session):
    bib1 = BibEntry(title="Book A", year=2010)
    bib2 = BibEntry(title="Book B", year=2015)
    global_session.add_all([bib1, bib2])
    global_session.flush()

    nodes, edges = collect_bibliography(global_session)
    node_ids = {n.node_id for n in nodes}
    assert f"bib:{bib1.id}" in node_ids
    assert f"bib:{bib2.id}" in node_ids
    for node in nodes:
        assert node.node_type == "bib_entry"
    assert edges == ()


# ── build_knowledge_graph ──────────────────────────────────────────────────


def test_build_knowledge_graph_global_only(global_session):
    bib = BibEntry(title="Test Book", year=2021)
    global_session.add(bib)
    global_session.flush()

    ex = Exercise(
        exercise_id="test-001",
        source_path="/path/test-001.tex",
        file_hash="aaa111",
        book_id=bib.id,
    )
    global_session.add(ex)
    global_session.flush()

    graph = build_knowledge_graph(global_session, local_session=None)
    assert isinstance(graph, KnowledgeGraph)
    node_ids = graph.node_ids()
    assert "exercise:test-001" in node_ids
    assert f"bib:{bib.id}" in node_ids


def test_build_knowledge_graph_both_dbs(global_session, local_session):
    note = Note(filename="my-note.md", reference="my-note")
    local_session.add(note)
    local_session.flush()

    bib = BibEntry(title="Another Book", year=2022)
    global_session.add(bib)
    global_session.flush()

    graph = build_knowledge_graph(global_session, local_session=local_session)
    node_ids = graph.node_ids()
    assert f"note:{note.id}" in node_ids
    assert f"bib:{bib.id}" in node_ids


def test_build_knowledge_graph_deduplicates_nodes(global_session, local_session):
    """Nodes with same node_id must appear only once."""
    note = Note(filename="dup.md", reference="dup")
    local_session.add(note)
    local_session.flush()

    graph = build_knowledge_graph(global_session, local_session=local_session)
    ids = [n.node_id for n in graph.nodes]
    assert len(ids) == len(set(ids))
