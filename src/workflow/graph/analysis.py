"""Pure-Python graph analysis for KnowledgeGraph.

All functions are side-effect-free and operate only on immutable
KnowledgeGraph objects.  No database access.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from workflow.graph.domain import GraphNode, KnowledgeGraph


@dataclass(frozen=True)
class GraphStats:
    """Summary statistics for a KnowledgeGraph."""

    total_nodes: int
    total_edges: int
    nodes_by_type: tuple[tuple[str, int], ...]
    edges_by_type: tuple[tuple[str, int], ...]
    orphan_count: int
    component_count: int


# ── Orphans ────────────────────────────────────────────────────────────────


def find_orphans(
    graph: KnowledgeGraph,
    node_type: str | None = None,
) -> tuple[GraphNode, ...]:
    """Return nodes with degree 0 (no edges in or out).

    If node_type is given, only nodes of that type are considered.
    """
    # Compute degree for every node that appears in at least one edge
    has_edge: set[str] = set()
    for e in graph.edges:
        has_edge.add(e.source_id)
        has_edge.add(e.target_id)

    result = [
        n for n in graph.nodes
        if n.node_id not in has_edge
        and (node_type is None or n.node_type == node_type)
    ]
    return tuple(result)


# ── Hubs ───────────────────────────────────────────────────────────────────


def find_hubs(
    graph: KnowledgeGraph,
    min_degree: int = 5,
) -> tuple[tuple[GraphNode, int], ...]:
    """Return nodes with undirected degree >= min_degree.

    Result is sorted by degree descending.
    """
    degree: Counter[str] = Counter()
    for e in graph.edges:
        degree[e.source_id] += 1
        degree[e.target_id] += 1

    node_map = {n.node_id: n for n in graph.nodes}
    hubs = [
        (node_map[nid], deg)
        for nid, deg in degree.items()
        if deg >= min_degree and nid in node_map
    ]
    hubs.sort(key=lambda x: x[1], reverse=True)
    return tuple(hubs)


# ── Connected components ───────────────────────────────────────────────────


def connected_components(
    graph: KnowledgeGraph,
) -> tuple[tuple[GraphNode, ...], ...]:
    """BFS-based undirected connected components.

    Returns a tuple of components, each component being a tuple of GraphNodes.
    Components are sorted by size descending.
    """
    if not graph.nodes:
        return ()

    adj = graph.adjacency()
    node_map = {n.node_id: n for n in graph.nodes}
    visited: set[str] = set()
    components: list[tuple[GraphNode, ...]] = []

    for node in graph.nodes:
        nid = node.node_id
        if nid in visited:
            continue
        # BFS from this node
        component: list[GraphNode] = []
        queue: deque[str] = deque([nid])
        visited.add(nid)
        while queue:
            current = queue.popleft()
            component.append(node_map[current])
            for neighbour in adj.get(current, []):
                if neighbour not in visited and neighbour in node_map:
                    visited.add(neighbour)
                    queue.append(neighbour)
        components.append(tuple(component))

    components.sort(key=len, reverse=True)
    return tuple(components)


# ── Neighbourhood subgraph ─────────────────────────────────────────────────


def neighbors(
    graph: KnowledgeGraph,
    node_id: str,
    depth: int = 1,
) -> KnowledgeGraph:
    """Return the subgraph containing node_id and all nodes within `depth` hops.

    Only edges whose both endpoints are in the subgraph are included.
    Returns an empty KnowledgeGraph if node_id is not in the graph.
    """
    node_ids = graph.node_ids()
    if node_id not in node_ids:
        return KnowledgeGraph(nodes=(), edges=())

    adj = graph.adjacency()
    # BFS up to depth hops
    visited: dict[str, int] = {node_id: 0}
    queue: deque[str] = deque([node_id])

    while queue:
        current = queue.popleft()
        current_depth = visited[current]
        if current_depth >= depth:
            continue
        for neighbour in adj.get(current, []):
            if neighbour not in visited and neighbour in node_ids:
                visited[neighbour] = current_depth + 1
                queue.append(neighbour)

    sub_ids = frozenset(visited.keys())
    node_map = {n.node_id: n for n in graph.nodes}
    sub_nodes = tuple(node_map[nid] for nid in sub_ids if nid in node_map)

    sub_edges = tuple(
        e for e in graph.edges
        if e.source_id in sub_ids and e.target_id in sub_ids
    )

    return KnowledgeGraph(nodes=sub_nodes, edges=sub_edges)


# ── Summary statistics ─────────────────────────────────────────────────────


def compute_stats(graph: KnowledgeGraph) -> GraphStats:
    """Compute summary statistics for a KnowledgeGraph."""
    type_counts: Counter[str] = Counter(n.node_type for n in graph.nodes)
    edge_type_counts: Counter[str] = Counter(e.edge_type for e in graph.edges)

    orphan_count = len(find_orphans(graph))
    comps = connected_components(graph)
    component_count = len(comps)

    return GraphStats(
        total_nodes=len(graph.nodes),
        total_edges=len(graph.edges),
        nodes_by_type=tuple(sorted(type_counts.items())),
        edges_by_type=tuple(sorted(edge_type_counts.items())),
        orphan_count=orphan_count,
        component_count=component_count,
    )


__all__ = [
    "GraphStats",
    "find_orphans",
    "find_hubs",
    "connected_components",
    "neighbors",
    "compute_stats",
]
