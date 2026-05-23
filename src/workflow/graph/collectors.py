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
    """Return Exercise nodes + edges to Content and BibEntry.

    Exercises are identified as "exercise:{exercise_id}".
    content_id FK → edge to "content:{content_id}".
    book_id FK    → edge to "bib:{book_id}".
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
        if ex.content_id is not None:
            edges.append(
                GraphEdge(
                    source_id=f"exercise:{ex.exercise_id}",
                    target_id=f"content:{ex.content_id}",
                    edge_type="exercise_content",
                )
            )
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
    from workflow.db.models.academic import (
        BibContent,
        Content,
        Course,
        CourseContent,
        Topic,
    )

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
    "build_knowledge_graph",
]
