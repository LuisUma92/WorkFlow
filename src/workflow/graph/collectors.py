"""Collectors for the WorkFlow knowledge graph.

Each collector queries one database (global or local) and returns
(nodes, edges) tuples of immutable domain objects.

build_knowledge_graph() merges all sources into a single KnowledgeGraph,
deduplicating nodes by node_id.

filter_graph_by_taxonomy() restricts a KnowledgeGraph to nodes reachable
from a taxonomy filter (MainTopic, DisciplineArea, or Topic).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph

__all__ = [
    "collect_notes",
    "collect_exercises",
    "collect_academic",
    "collect_bibliography",
    "collect_note_edges",
    "collect_note_concepts",
    "collect_exercise_concepts",
    "build_knowledge_graph",
    "resolve_taxonomy_filter",
    "filter_graph_by_taxonomy",
    "TaxonomyFilter",
]


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


# ── Taxonomy filter ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TaxonomyFilter:
    """Resolved taxonomy filter — integer ID sets after slug resolution.

    Any field left as an empty frozenset means "no restriction on that axis".
    The AND-intersection is computed in filter_graph_by_taxonomy().
    """

    topic_ids: frozenset[int] = frozenset()
    discipline_area_ids: frozenset[int] = frozenset()
    main_topic_ids: frozenset[int] = frozenset()

    def is_empty(self) -> bool:
        """True when no filter is active — graph should pass through unchanged."""
        return not (self.topic_ids or self.discipline_area_ids or self.main_topic_ids)


def resolve_taxonomy_filter(
    session: Session,
    *,
    main_topic: str | None = None,
    discipline_area: str | None = None,
    topic: str | None = None,
) -> TaxonomyFilter:
    """Resolve slug-or-numeric-id strings to a TaxonomyFilter.

    Each argument is either a string slug (``code`` column) or a numeric id
    string.  Unknown slugs raise ``ValueError`` with a descriptive message.
    Numeric ids that do not exist also raise ``ValueError``.

    Returns a :class:`TaxonomyFilter` with resolved integer ID sets.
    """
    from workflow.db.models.knowledge import DisciplineArea, MainTopic, Topic

    def _resolve_main_topic(slug_or_id: str) -> int:
        if slug_or_id.isdigit():
            mt = session.get(MainTopic, int(slug_or_id))
            if mt is None:
                raise ValueError(f"MainTopic id={slug_or_id!r} not found")
            return mt.id
        mt = session.scalars(
            select(MainTopic).where(MainTopic.code == slug_or_id)
        ).first()
        if mt is None:
            raise ValueError(f"MainTopic code={slug_or_id!r} not found")
        return mt.id

    def _resolve_discipline_area(slug_or_id: str) -> int:
        if slug_or_id.isdigit():
            da = session.get(DisciplineArea, int(slug_or_id))
            if da is None:
                raise ValueError(f"DisciplineArea id={slug_or_id!r} not found")
            return da.id
        da = session.scalars(
            select(DisciplineArea).where(DisciplineArea.code == slug_or_id)
        ).first()
        if da is None:
            raise ValueError(f"DisciplineArea code={slug_or_id!r} not found")
        return da.id

    def _resolve_topic(slug_or_id: str) -> int:
        if slug_or_id.isdigit():
            tp = session.get(Topic, int(slug_or_id))
            if tp is None:
                raise ValueError(f"Topic id={slug_or_id!r} not found")
            return tp.id
        # Topic has no unique slug column — fall back to name (case-insensitive)
        tp = session.scalars(
            select(Topic).where(Topic.name == slug_or_id)
        ).first()
        if tp is None:
            raise ValueError(
                f"Topic name={slug_or_id!r} not found "
                "(Topic has no slug column; pass numeric id or exact name)"
            )
        return tp.id

    mt_ids: frozenset[int] = frozenset()
    da_ids: frozenset[int] = frozenset()
    tp_ids: frozenset[int] = frozenset()

    if main_topic is not None:
        mt_ids = frozenset([_resolve_main_topic(main_topic)])
    if discipline_area is not None:
        da_ids = frozenset([_resolve_discipline_area(discipline_area)])
    if topic is not None:
        tp_ids = frozenset([_resolve_topic(topic)])

    return TaxonomyFilter(
        topic_ids=tp_ids,
        discipline_area_ids=da_ids,
        main_topic_ids=mt_ids,
    )


def _collect_topic_ids_for_filter(
    session: Session,
    tf: TaxonomyFilter,
) -> frozenset[int]:
    """Expand a TaxonomyFilter to the set of concrete Topic ids to retain.

    Traversal:
      MainTopic  → MainTopicSyllabus → Topic
      DisciplineArea → Topic (discipline_area_id FK)
      Topic      → Topic (direct)

    Returns the intersection if multiple axes are set, so that only topics
    that satisfy ALL active filters survive.
    """
    from workflow.db.models.knowledge import MainTopicSyllabus, Topic

    axis_sets: list[frozenset[int]] = []

    if tf.main_topic_ids:
        rows = session.scalars(
            select(MainTopicSyllabus).where(
                MainTopicSyllabus.main_topic_id.in_(tf.main_topic_ids)
            )
        ).all()
        axis_sets.append(frozenset(r.topic_id for r in rows))

    if tf.discipline_area_ids:
        rows = session.scalars(
            select(Topic).where(
                Topic.discipline_area_id.in_(tf.discipline_area_ids)
            )
        ).all()
        axis_sets.append(frozenset(r.id for r in rows))

    if tf.topic_ids:
        axis_sets.append(tf.topic_ids)

    if not axis_sets:
        return frozenset()

    result = axis_sets[0]
    for s in axis_sets[1:]:
        result = result & s
    return result


def filter_graph_by_taxonomy(
    kg: KnowledgeGraph,
    session: Session,
    tf: TaxonomyFilter,
) -> KnowledgeGraph:
    """Return a subgraph containing only nodes reachable from the taxonomy filter.

    If *tf* is empty (no filter active) the original graph is returned unchanged.

    Reachability is defined as:
    - ``content:{id}``   where content.topic_id in allowed_topic_ids
    - ``topic:{id}``     where topic.id in allowed_topic_ids
    - ``concept:{id}``   where concept.content.topic_id in allowed_topic_ids
    - ``note:{id}``      where note.main_topic_id resolves to an allowed topic
                         (via MainTopicSyllabus) OR note has a NoteConcept
                         linking to an allowed concept
    - ``exercise:{id}``  via ExerciseConcept → concept → content → topic
    - All edges whose BOTH endpoints are in the surviving node set.

    Notes whose ``main_topic_id`` is NULL are included only when they link
    to a surviving concept (via NoteConcept).
    """
    if tf.is_empty():
        return kg

    from workflow.db.models.exercises import Exercise, ExerciseConcept
    from workflow.db.models.knowledge import Concept, Content, Topic
    from workflow.db.models.notes import Note, NoteConcept

    allowed_topic_ids = _collect_topic_ids_for_filter(session, tf)

    # Empty intersection → empty graph (valid AND-filter result)
    if not allowed_topic_ids:
        return KnowledgeGraph(nodes=(), edges=())

    # Allowed content ids
    allowed_content_ids: frozenset[int] = frozenset(
        c.id
        for c in session.scalars(
            select(Content).where(Content.topic_id.in_(allowed_topic_ids))
        ).all()
    )

    # Allowed concept ids
    allowed_concept_ids: frozenset[int] = frozenset(
        c.id
        for c in session.scalars(
            select(Concept).where(Concept.content_id.in_(allowed_content_ids))
        ).all()
    )

    # Allowed note ids (via main_topic_id OR via NoteConcept → concept)
    note_ids_via_concept: frozenset[int] = frozenset(
        row.note_id
        for row in session.scalars(
            select(NoteConcept).where(
                NoteConcept.concept_id.in_(allowed_concept_ids)
            )
        ).all()
    )
    # Notes with direct main_topic_id — main_topic_id resolves to a MainTopic
    # whose syllabus covers an allowed topic.
    allowed_note_ids = note_ids_via_concept
    if tf.main_topic_ids or tf.discipline_area_ids:
        # Include notes that have a main_topic_id in the syllabus intersection
        from workflow.db.models.knowledge import MainTopicSyllabus
        from workflow.db.models.notes import Note as _Note

        mt_ids_for_notes: set[int] = set()
        if tf.main_topic_ids:
            mt_ids_for_notes.update(tf.main_topic_ids)
        if tf.discipline_area_ids:
            # Collect MainTopics whose discipline_area is in the filter
            from workflow.db.models.knowledge import MainTopic
            mts = session.scalars(
                select(MainTopic).where(
                    MainTopic.discipline_area_id.in_(tf.discipline_area_ids)
                )
            ).all()
            mt_ids_for_notes.update(m.id for m in mts)

        if mt_ids_for_notes:
            direct_notes = session.scalars(
                select(_Note).where(_Note.main_topic_id.in_(mt_ids_for_notes))
            ).all()
            allowed_note_ids = allowed_note_ids | frozenset(n.id for n in direct_notes)

    # Allowed exercise ids (via ExerciseConcept → concept)
    ec_rows = session.scalars(
        select(ExerciseConcept).where(
            ExerciseConcept.concept_id.in_(allowed_concept_ids)
        )
    ).all()
    allowed_exercise_int_ids: frozenset[int] = frozenset(r.exercise_id for r in ec_rows)
    exercise_id_to_str: dict[int, str] = {}
    if allowed_exercise_int_ids:
        exes = session.scalars(
            select(Exercise).where(Exercise.id.in_(allowed_exercise_int_ids))
        ).all()
        exercise_id_to_str = {ex.id: ex.exercise_id for ex in exes}

    # Build allowed node_id set
    allowed_node_ids: set[str] = set()
    allowed_node_ids.update(f"topic:{tid}" for tid in allowed_topic_ids)
    allowed_node_ids.update(f"content:{cid}" for cid in allowed_content_ids)
    allowed_node_ids.update(f"concept:{cid}" for cid in allowed_concept_ids)
    allowed_node_ids.update(f"note:{nid}" for nid in allowed_note_ids)
    allowed_node_ids.update(
        f"exercise:{eid_str}" for eid_str in exercise_id_to_str.values()
    )

    filtered_nodes = tuple(n for n in kg.nodes if n.node_id in allowed_node_ids)
    surviving = frozenset(n.node_id for n in filtered_nodes)
    filtered_edges = tuple(
        e for e in kg.edges
        if e.source_id in surviving and e.target_id in surviving
    )

    return KnowledgeGraph(nodes=filtered_nodes, edges=filtered_edges)
