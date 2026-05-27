"""Collectors for the WorkFlow knowledge graph.

Each collector queries one database (global or local) and returns
(nodes, edges) tuples of immutable domain objects.

build_knowledge_graph() merges all sources into a single KnowledgeGraph,
deduplicating nodes by node_id.
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select

from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph


# ── Notes collector (GlobalBase, ITEP-0011 P3) ─────────────────────────────


def collect_notes(
    session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return Note nodes + Link edges + Citation edges from the global DB.

    ITEP-0011 P3: notes live on GlobalBase. ``session`` is a GlobalBase
    session.

    Notes are identified as "note:{id}".
    Link edges connect source note → target note (resolved via Label).
    Citation edges connect note → "bib:{citationkey}".
    """
    from workflow.db.models.notes import Citation, Label, Link, Note

    notes = session.scalars(select(Note)).all()
    if not notes:
        return (), ()

    nodes: list[GraphNode] = [
        GraphNode(node_id=f"note:{n.id}", node_type="note", label=n.filename)
        for n in notes
    ]

    labels = session.scalars(select(Label)).all()
    label_to_note: dict[int, int] = {lbl.id: lbl.note_id for lbl in labels}

    edges: list[GraphEdge] = []

    links = session.scalars(select(Link)).all()
    for lnk in links:
        target_note_id = label_to_note.get(lnk.target_id)
        if target_note_id is not None:
            edges.append(
                GraphEdge(
                    source_id=f"note:{lnk.source_id}",
                    target_id=f"note:{target_note_id}",
                    edge_type="link",
                )
            )

    citations = session.scalars(select(Citation)).all()
    for cit in citations:
        edges.append(
            GraphEdge(
                source_id=f"note:{cit.note_id}",
                target_id=f"bib:{cit.citationkey}",
                edge_type="citation",
                label=cit.citationkey,
            )
        )

    return tuple(nodes), tuple(edges)


# ── Exercises collector (global workflow.db) ────────────────────────────────


def collect_exercises(
    global_session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return Exercise nodes + edges to BibEntry.

    Exercises are identified as "exercise:{exercise_id}".
    book_id FK    → edge to "bib:{book_id}".

    Note: Exercise.content_id was dropped in the ORM reshape (Phase 4);
    exercise→content edges are now expressed via ExerciseConcept→Concept→Content.
    """
    from workflow.db.models.exercises import Exercise

    exercises = global_session.scalars(select(Exercise)).all()
    if not exercises:
        return (), ()

    nodes: list[GraphNode] = [
        GraphNode(
            node_id=f"exercise:{ex.exercise_id}",
            node_type="exercise",
            label=ex.exercise_id,
        )
        for ex in exercises
    ]

    edges: list[GraphEdge] = []
    for ex in exercises:
        if ex.book_id is not None:
            edges.append(
                GraphEdge(
                    source_id=f"exercise:{ex.exercise_id}",
                    target_id=f"bib:{ex.book_id}",
                    edge_type="exercise_book",
                )
            )

    return tuple(nodes), tuple(edges)


# ── Academic collector (global workflow.db) ─────────────────────────────────


def collect_academic(
    global_session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return Content, Topic, Course nodes + BibContent and CourseContent edges.

    Content  → "content:{id}"
    Topic    → "topic:{id}"
    Course   → "course:{id}"
    BibContent edge:   "bib:{bib_entry_id}" → "content:{content_id}"
    CourseContent edge: "course:{course_id}" → "content:{content_id}"
    """
    from workflow.db.models.academic import Course, CourseContent
    from workflow.db.models.bibliography import BibContent
    from workflow.db.models.knowledge import Content, Topic

    contents = global_session.scalars(select(Content)).all()
    topics = global_session.scalars(select(Topic)).all()
    courses = global_session.scalars(select(Course)).all()

    if not (contents or topics or courses):
        return (), ()

    nodes: list[GraphNode] = []

    for c in contents:
        nodes.append(
            GraphNode(node_id=f"content:{c.id}", node_type="content", label=c.name)
        )
    for t in topics:
        nodes.append(
            GraphNode(node_id=f"topic:{t.id}", node_type="topic", label=t.name)
        )
    for course in courses:
        nodes.append(
            GraphNode(
                node_id=f"course:{course.id}", node_type="course", label=course.name
            )
        )

    edges: list[GraphEdge] = []

    # BibContent edges
    bib_contents = global_session.scalars(select(BibContent)).all()
    for bc in bib_contents:
        edges.append(
            GraphEdge(
                source_id=f"bib:{bc.bib_entry_id}",
                target_id=f"content:{bc.content_id}",
                edge_type="bib_content",
            )
        )

    # CourseContent edges
    course_contents = global_session.scalars(select(CourseContent)).all()
    for cc in course_contents:
        edges.append(
            GraphEdge(
                source_id=f"course:{cc.course_id}",
                target_id=f"content:{cc.content_id}",
                edge_type="course_content",
            )
        )

    return tuple(nodes), tuple(edges)


# ── Bibliography collector (global workflow.db) ─────────────────────────────


def collect_bibliography(
    global_session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return BibEntry nodes (no edges — BibEntry is referenced by others).

    BibEntry nodes are identified as "bib:{id}".
    """
    from workflow.db.models.bibliography import BibEntry

    entries = global_session.scalars(select(BibEntry)).all()
    if not entries:
        return (), ()

    nodes = tuple(
        GraphNode(
            node_id=f"bib:{e.id}",
            node_type="bib_entry",
            label=e.bibkey or e.title or f"bib:{e.id}",
        )
        for e in entries
    )
    return nodes, ()


# ── Note-edge collector (ITEP-0013 P2.6) ────────────────────────────────────


def collect_note_edges(
    session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return GraphEdge objects for resolved NoteEdges (ITEP-0013).

    Only edges with target_id IS NOT NULL are included — unresolved edges
    have no target node in the graph yet.

    edge_type format: ``"note_edge:<edge_class>"``  e.g. ``"note_edge:structural"``
    label: the relation_type string (e.g. ``"refines"``)
    """
    from workflow.db.models.notes import NoteEdge

    rows = session.scalars(
        select(NoteEdge).where(NoteEdge.target_id.is_not(None))
    ).all()

    if not rows:
        return (), ()

    edges = tuple(
        GraphEdge(
            source_id=f"note:{row.source_id}",
            target_id=f"note:{row.target_id}",
            edge_type=f"note_edge:{row.edge_class}",
            label=row.relation_type,
        )
        for row in rows
    )
    return (), edges


# ── Note-concept collector (ITEP-0012) ──────────────────────────────────────


def collect_note_concepts(
    session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return GraphNode objects for Concepts + GraphEdge for each NoteConcept row.

    Concept nodes are identified as ``"concept:<id>"``; label is concept.code.
    Edge type is ``"note_concept"``; label is concept.code.
    Concept nodes are deduplicated (multiple notes can share the same concept).
    """
    from workflow.db.models.knowledge import Concept
    from workflow.db.models.notes import NoteConcept

    rows = session.scalars(select(NoteConcept)).all()
    if not rows:
        return (), ()

    concept_ids = {row.concept_id for row in rows}
    concepts = {
        c.id: c
        for c in session.scalars(
            select(Concept).where(Concept.id.in_(concept_ids))
        ).all()
    }

    nodes = tuple(
        GraphNode(node_id=f"concept:{c.id}", node_type="concept", label=c.code)
        for c in concepts.values()
    )
    edges = tuple(
        GraphEdge(
            source_id=f"note:{row.note_id}",
            target_id=f"concept:{row.concept_id}",
            edge_type="note_concept",
            label=concepts[row.concept_id].code,
        )
        for row in rows
        if row.concept_id in concepts
    )
    return nodes, edges


# ── Exercise-concept collector (Phase 4B) ───────────────────────────────────


def collect_exercise_concepts(
    global_session: Session,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return GraphNode objects for Concepts + GraphEdge for each ExerciseConcept row.

    Concept nodes are identified as ``"concept:<id>"``; label is concept.code.
    Exercise nodes are identified as ``"exercise:<exercise_id>"``; label is exercise_id.
    Edge type is ``"exercise→concept"``; label is concept.code.
    Concept nodes are deduplicated (multiple exercises can share the same concept).
    """
    from workflow.db.models.exercises import Exercise, ExerciseConcept
    from workflow.db.models.knowledge import Concept

    rows = global_session.scalars(select(ExerciseConcept)).all()
    if not rows:
        return (), ()

    concept_ids = {row.concept_id for row in rows}
    concepts = {
        c.id: c
        for c in global_session.scalars(
            select(Concept).where(Concept.id.in_(concept_ids))
        ).all()
    }

    exercise_int_ids = {row.exercise_id for row in rows}
    exercises = {
        ex.id: ex
        for ex in global_session.scalars(
            select(Exercise).where(Exercise.id.in_(exercise_int_ids))
        ).all()
    }

    nodes = tuple(
        GraphNode(node_id=f"concept:{c.id}", node_type="concept", label=c.code)
        for c in concepts.values()
    )
    exercise_nodes = tuple(
        GraphNode(
            node_id=f"exercise:{ex.exercise_id}",
            node_type="exercise",
            label=ex.exercise_id,
        )
        for ex in exercises.values()
    )
    edges = tuple(
        GraphEdge(
            source_id=f"exercise:{exercises[row.exercise_id].exercise_id}",
            target_id=f"concept:{row.concept_id}",
            edge_type="exercise→concept",
            label=concepts[row.concept_id].code,
        )
        for row in rows
        if row.exercise_id in exercises and row.concept_id in concepts
    )
    return exercise_nodes + nodes, edges


# ── Master builder ──────────────────────────────────────────────────────────


def build_knowledge_graph(
    global_session: Session,
) -> KnowledgeGraph:
    """Collect all sources, merge, and deduplicate nodes by node_id.

    ITEP-0011 P3: all sources (notes, exercises, academic, bibliography,
    note-edges) live on GlobalBase, so a single session is sufficient.
    """
    all_nodes: list[GraphNode] = []
    all_edges: list[GraphEdge] = []

    for collector in (
        collect_notes,
        collect_exercises,
        collect_academic,
        collect_bibliography,
        collect_note_edges,
        collect_note_concepts,
        collect_exercise_concepts,
    ):
        nodes, edges = collector(global_session)
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    # Deduplicate nodes: keep first occurrence of each node_id
    seen_ids: set[str] = set()
    deduped_nodes: list[GraphNode] = []
    for node in all_nodes:
        if node.node_id not in seen_ids:
            seen_ids.add(node.node_id)
            deduped_nodes.append(node)

    return KnowledgeGraph(nodes=tuple(deduped_nodes), edges=tuple(all_edges))


__all__ = [
    "collect_notes",
    "collect_exercises",
    "collect_academic",
    "collect_bibliography",
    "collect_note_edges",
    "collect_note_concepts",
    "collect_exercise_concepts",
    "build_knowledge_graph",
]
