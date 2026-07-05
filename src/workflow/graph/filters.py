"""Graph filter helpers (Wave 4).

Pure functions used by ``workflow.graph.cli`` to build, expand, and filter
``KnowledgeGraph`` instances (full-graph construction, BFS depth expansion,
cluster selection, tag-based include/exclude filtering). Extracted from
``graph/cli.py`` (architect HIGH, W4 review) to separate CLI wiring from
filter logic. No behavior change from the original ``cli.py`` implementation.
"""

from __future__ import annotations

import re as _re
from collections import deque as _deque

from sqlalchemy import Engine
from sqlalchemy.orm import Session

import click

from workflow.db.engine import init_global_db
from workflow.graph.collectors import build_knowledge_graph
from workflow.graph.domain import GraphNode, KnowledgeGraph

__all__ = [
    "_build_full_graph",
    "_expand_by_depth",
    "_parse_cluster_name",
    "_filter_by_cluster",
    "_filter_by_tags",
]


def _build_full_graph(
    project: str,
    engine: Engine | None = None,
) -> KnowledgeGraph:
    """Build the full knowledge graph without any taxonomy filter."""
    del project  # reserved for ITEP-0011 P5 routing
    global_engine = engine or init_global_db()
    with Session(global_engine) as gsession:
        return build_knowledge_graph(gsession)


def _expand_by_depth(
    full_kg: KnowledgeGraph,
    seed_kg: KnowledgeGraph,
    depth: int,
) -> KnowledgeGraph:
    """Expand *seed_kg* by up to *depth* hops in *full_kg*.

    Multi-source BFS from every node in *seed_kg*, traversing edges in
    *full_kg*.  Returns a subgraph containing all reachable nodes and the
    induced edges from *full_kg*.

    depth=0 returns *seed_kg* unchanged.
    """
    if depth <= 0:
        return seed_kg

    seed_ids = seed_kg.node_ids()
    all_node_ids = full_kg.node_ids()
    adj = full_kg.adjacency()

    # Multi-source BFS: start at every seed node simultaneously.
    visited: dict[str, int] = {nid: 0 for nid in seed_ids if nid in all_node_ids}
    queue: _deque[tuple[str, int]] = _deque((nid, 0) for nid in visited)

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited and neighbor in all_node_ids:
                visited[neighbor] = current_depth + 1
                queue.append((neighbor, current_depth + 1))

    expanded_ids = frozenset(visited.keys())
    node_map = {n.node_id: n for n in full_kg.nodes}
    exp_nodes = tuple(node_map[nid] for nid in expanded_ids if nid in node_map)
    exp_edges = tuple(
        e for e in full_kg.edges
        if e.source_id in expanded_ids and e.target_id in expanded_ids
    )
    return KnowledgeGraph(nodes=exp_nodes, edges=exp_edges)


def _parse_cluster_name(name: str, max_count: int) -> int:
    """Parse a cluster name to a 0-based index.

    Accepts plain integers (``"1"``) or ``graph clusters``-style names
    (``"Cluster 1"``).  Raises ``click.ClickException`` on invalid input.
    """
    m = _re.fullmatch(r'(?:cluster\s+)?(\d+)', name.strip(), _re.IGNORECASE)
    if not m:
        raise click.ClickException(
            f"Invalid cluster name {name!r}. Use a number (1-based) or 'Cluster N'."
        )
    idx = int(m.group(1)) - 1  # convert to 0-based
    if idx < 0 or idx >= max_count:
        raise click.ClickException(
            f"Cluster {name!r} not found (valid range: 1–{max_count})."
        )
    return idx


def _filter_by_cluster(kg: KnowledgeGraph, cluster_name: str) -> KnowledgeGraph:
    """Return the subgraph matching the named community.

    Requires networkx; raises ``click.ClickException`` if unavailable.
    """
    from workflow.graph.clustering import detect_communities

    communities = detect_communities(kg)
    if communities is None:
        raise click.ClickException(
            "networkx is not installed. Install it with: pip install networkx"
        )
    if not communities:
        raise click.ClickException("No clusters found (graph is empty).")

    idx = _parse_cluster_name(cluster_name, len(communities))
    community = communities[idx]
    comm_ids = frozenset(n.node_id for n in community)
    sub_edges = tuple(
        e for e in kg.edges
        if e.source_id in comm_ids and e.target_id in comm_ids
    )
    return KnowledgeGraph(nodes=community, edges=sub_edges)


def _filter_by_tags(
    kg: KnowledgeGraph,
    include_tags: str | None,
    exclude_tags: str | None,
) -> KnowledgeGraph:
    """Filter graph nodes by real DB-backed ``GraphNode.tags`` membership.

    *include_tags* / *exclude_tags* are comma-separated strings, matched
    case-insensitively against each node's ``tags`` set (real ``Tag.name``
    rows propagated by ``collect_notes``, ITEP-0011/freeze-window Phase 5).
    A node is kept when it has at least one include-tag (if any specified)
    and none of the exclude-tags. Nodes with no tags (e.g. non-note types,
    or notes with zero NoteTag rows) never match an include filter and are
    dropped whenever ``include_tags`` is set.

    This replaces the earlier W4 label-substring workaround — see
    ``docs/ADR`` freeze-window plan Phase 5.
    """
    inc = [t.strip().lower() for t in include_tags.split(",") if t.strip()] if include_tags else []
    exc = [t.strip().lower() for t in exclude_tags.split(",") if t.strip()] if exclude_tags else []

    def _keep(node: GraphNode) -> bool:
        tags = {t.lower() for t in node.tags}
        if inc and not any(t in tags for t in inc):
            return False
        if exc and any(t in tags for t in exc):
            return False
        return True

    sub_nodes = tuple(n for n in kg.nodes if _keep(n))
    sub_ids = frozenset(n.node_id for n in sub_nodes)
    sub_edges = tuple(
        e for e in kg.edges
        if e.source_id in sub_ids and e.target_id in sub_ids
    )
    return KnowledgeGraph(nodes=sub_nodes, edges=sub_edges)
