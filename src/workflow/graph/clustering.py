"""Optional networkx-based community detection for WorkFlow knowledge graph.

If networkx is not installed, detect_communities returns None gracefully.
"""
from __future__ import annotations

from workflow.graph.domain import KnowledgeGraph, GraphNode


def detect_communities(
    graph: KnowledgeGraph,
) -> tuple[tuple[GraphNode, ...], ...] | None:
    """Detect communities via greedy modularity algorithm.

    Returns a tuple of node groups (one per community), or None if networkx
    is not installed.  Returns an empty tuple for an empty graph.
    """
    try:
        import networkx as nx
        from networkx.algorithms.community import greedy_modularity_communities
    except ImportError:
        return None

    G = nx.Graph()
    for node in graph.nodes:
        G.add_node(node.node_id)
    for edge in graph.edges:
        if edge.source_id in G and edge.target_id in G:
            G.add_edge(edge.source_id, edge.target_id)

    if len(G) == 0:
        return ()

    communities = greedy_modularity_communities(G)

    node_map = {n.node_id: n for n in graph.nodes}
    return tuple(
        tuple(node_map[nid] for nid in community if nid in node_map)
        for community in communities
    )


__all__ = ["detect_communities"]
