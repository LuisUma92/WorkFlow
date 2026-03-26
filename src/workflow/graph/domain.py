"""Domain objects for the WorkFlow knowledge graph.

Immutable value types representing nodes, edges, and the full graph.
All types are frozen dataclasses — safe to hash and use in sets.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNode:
    """A node in the knowledge graph.

    node_id format:  "<type>:<key>"  e.g. "note:42", "exercise:phys-gauss-001"
    node_type:       "note" | "exercise" | "bib_entry" | "content" | "topic" | "course"
    label:           human-readable display string
    """

    node_id: str
    node_type: str
    label: str


@dataclass(frozen=True)
class GraphEdge:
    """A directed edge in the knowledge graph.

    edge_type values:
        "link"             — note → note (via Label)
        "citation"         — note → bib_entry (via Citation.citationkey)
        "exercise_content" — exercise → content
        "exercise_book"    — exercise → bib_entry (source textbook)
        "bib_content"      — bib_entry → content (BibContent join)
        "course_content"   — course → content (CourseContent join)
    """

    source_id: str
    target_id: str
    edge_type: str
    label: str = ""


@dataclass(frozen=True)
class KnowledgeGraph:
    """Immutable snapshot of the full knowledge graph.

    nodes and edges are stored as tuples to preserve insertion order
    and remain hashable.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def node_ids(self) -> frozenset[str]:
        """Return the set of all node IDs."""
        return frozenset(n.node_id for n in self.nodes)

    def adjacency(self) -> dict[str, list[str]]:
        """Build an undirected adjacency list.

        Returns a dict mapping each node_id to a list of neighbouring node_ids.
        Edges that reference node_ids not present in the graph are silently
        included in the neighbour list (sparse/dangling references).
        """
        adj: dict[str, list[str]] = {n.node_id: [] for n in self.nodes}
        for e in self.edges:
            if e.source_id in adj:
                adj[e.source_id].append(e.target_id)
            if e.target_id in adj:
                adj[e.target_id].append(e.source_id)
        return adj


__all__ = ["GraphNode", "GraphEdge", "KnowledgeGraph"]
