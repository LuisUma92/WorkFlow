"""Pure-Python graph analysis for KnowledgeGraph.

All functions are side-effect-free and operate only on immutable
KnowledgeGraph objects.  No database access.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from workflow.graph.domain import GraphNode, KnowledgeGraph


@dataclass(frozen=True)
class NeighborInfo:
    """A single neighbor entry from BFS traversal.

    node:       the neighboring GraphNode
    depth:      BFS hop distance from the source (>= 1)
    edge_type:  edge_type of the edge that connects this neighbor to its BFS
                predecessor, or None if not determinable
    """

    node: GraphNode
    depth: int
    edge_type: str | None


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


# ── Detailed neighbourhood (for JSON output) ──────────────────────────────


def _build_edge_map(graph: KnowledgeGraph) -> dict[tuple[str, str], str]:
    """Return undirected (src, tgt) → edge_type lookup (last-write wins)."""
    em: dict[tuple[str, str], str] = {}
    for e in graph.edges:
        em[(e.source_id, e.target_id)] = e.edge_type
        em[(e.target_id, e.source_id)] = e.edge_type
    return em


def _bfs_with_parents(
    start: str,
    depth: int,
    adj: dict[str, list[str]],
    node_ids: frozenset[str],
) -> dict[str, tuple[int, str | None]]:
    """BFS from *start* up to *depth* hops.

    Returns  {node_id: (hop_depth, parent_id_or_None)}.
    """
    visited: dict[str, tuple[int, str | None]] = {start: (0, None)}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        current_depth, _ = visited[current]
        if current_depth >= depth:
            continue
        for neighbour in adj.get(current, []):
            if neighbour not in visited and neighbour in node_ids:
                visited[neighbour] = (current_depth + 1, current)
                queue.append(neighbour)
    return visited


def neighbors_detailed(
    graph: KnowledgeGraph,
    node_id: str,
    depth: int = 1,
) -> list[NeighborInfo]:
    """Return a list of NeighborInfo for every node within `depth` hops of node_id.

    The source node itself is excluded from the result.
    Nodes are ordered by depth (ascending), then insertion order within each level.

    ``edge_type`` on each NeighborInfo is the edge_type of the edge linking that
    neighbor to its BFS predecessor (best-effort; None if not determinable).

    Returns an empty list when node_id is not in the graph.
    """
    node_ids = graph.node_ids()
    if node_id not in node_ids:
        return []

    edge_map = _build_edge_map(graph)
    node_map = {n.node_id: n for n in graph.nodes}
    visited = _bfs_with_parents(node_id, depth, graph.adjacency(), node_ids)

    result: list[NeighborInfo] = []
    for nid, (d, parent) in visited.items():
        if nid == node_id or nid not in node_map:
            continue
        etype: str | None = edge_map.get((parent, nid)) if parent else None
        result.append(NeighborInfo(node=node_map[nid], depth=d, edge_type=etype))

    result.sort(key=lambda ni: ni.depth)
    return result


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


# ── Directed traversal ────────────────────────────────────────────────────


def directed_bfs(
    start_id: str,
    adj: dict[str, list[str]],
    max_depth: int,
    node_budget: int,
) -> dict[str, int]:
    """BFS from *start_id* using a directed adjacency map.

    Args:
        start_id: The node to start from.
        adj: Directed adjacency map {node_id: [neighbor_id, ...]}.
        max_depth: Maximum hop depth (inclusive).
        node_budget: Stop when this many nodes have been collected.

    Returns:
        ``{node_id: depth}`` for all reachable nodes up to the bounds.
        The start node is included at depth 0.
    """
    if node_budget <= 0:
        return {}
    visited: dict[str, int] = {start_id: 0}
    queue: deque[str] = deque([start_id])
    while queue:
        if len(visited) >= node_budget:
            break
        current = queue.popleft()
        d = visited[current]
        if d >= max_depth:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited[neighbor] = d + 1
                queue.append(neighbor)
                if len(visited) >= node_budget:
                    break
    return visited


# ── Lineage roots ─────────────────────────────────────────────────────────


def find_lineage_roots(
    graph: KnowledgeGraph,
    node_type: str | None = None,
) -> tuple[GraphNode, ...]:
    """Return nodes that have outgoing structural edges but no incoming structural edges.

    These are "lineage roots" in the sense that they are the starting points
    of derivative chains — they were derived from others, but nothing was
    derived from them.

    If *node_type* is given, only nodes of that type are considered.
    """
    _structural = "note_edge:structural"

    has_incoming: set[str] = set()
    has_outgoing: set[str] = set()

    for e in graph.edges:
        if e.edge_type == _structural:
            has_outgoing.add(e.source_id)
            has_incoming.add(e.target_id)

    node_map = {n.node_id: n for n in graph.nodes}
    result = [
        node_map[nid]
        for nid in has_outgoing
        if nid not in has_incoming
        and nid in node_map
        and (node_type is None or node_map[nid].node_type == node_type)
    ]
    return tuple(result)


__all__ = [
    "GraphStats",
    "NeighborInfo",
    "find_orphans",
    "find_hubs",
    "connected_components",
    "neighbors",
    "neighbors_detailed",
    "compute_stats",
    "directed_bfs",
    "find_lineage_roots",
]
