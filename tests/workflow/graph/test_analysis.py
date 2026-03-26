"""Tests for workflow.graph.analysis — pure Python graph analysis."""
from __future__ import annotations

import pytest

from workflow.graph.analysis import (
    GraphStats,
    compute_stats,
    connected_components,
    find_hubs,
    find_orphans,
    neighbors,
)
from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph


# ── Helpers ────────────────────────────────────────────────────────────────


def _node(nid: str, ntype: str = "note") -> GraphNode:
    return GraphNode(node_id=nid, node_type=ntype, label=nid)


def _edge(src: str, tgt: str, etype: str = "link") -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type=etype)


def _graph(*node_ids: str, edges: list[tuple[str, str]] | None = None) -> KnowledgeGraph:
    nodes = tuple(_node(nid) for nid in node_ids)
    edge_objs = tuple(_edge(s, t) for s, t in (edges or []))
    return KnowledgeGraph(nodes=nodes, edges=edge_objs)


# ── find_orphans ───────────────────────────────────────────────────────────


def test_find_orphans_empty_graph():
    g = _graph()
    assert find_orphans(g) == ()


def test_find_orphans_none_when_all_connected():
    g = _graph("a", "b", edges=[("a", "b")])
    assert find_orphans(g) == ()


def test_find_orphans_some():
    g = _graph("a", "b", "c", edges=[("a", "b")])
    orphans = find_orphans(g)
    ids = {n.node_id for n in orphans}
    assert ids == {"c"}


def test_find_orphans_all():
    g = _graph("x", "y", "z")
    assert len(find_orphans(g)) == 3


def test_find_orphans_filter_by_type():
    nodes = (
        _node("note:1", "note"),
        _node("note:2", "note"),
        _node("bib:1", "bib_entry"),
    )
    edges = (_edge("note:1", "note:2"),)
    g = KnowledgeGraph(nodes=nodes, edges=edges)

    # Filter to bib_entry orphans
    bib_orphans = find_orphans(g, node_type="bib_entry")
    ids = {n.node_id for n in bib_orphans}
    assert ids == {"bib:1"}

    # No note orphans (note:1 and note:2 are connected)
    note_orphans = find_orphans(g, node_type="note")
    assert note_orphans == ()


# ── find_hubs ──────────────────────────────────────────────────────────────


def test_find_hubs_empty_graph():
    g = _graph()
    assert find_hubs(g) == ()


def test_find_hubs_none_meet_threshold():
    g = _graph("a", "b", edges=[("a", "b")])
    # Default min_degree=5, only degree 1 nodes
    assert find_hubs(g) == ()


def test_find_hubs_returns_sorted_by_degree():
    # a connects to b,c,d,e,f (degree 5)
    # b connects to a (degree 1)
    nodes = tuple(_node(nid) for nid in ["a", "b", "c", "d", "e", "f"])
    edges = tuple(_edge("a", nid) for nid in ["b", "c", "d", "e", "f"])
    g = KnowledgeGraph(nodes=nodes, edges=edges)

    hubs = find_hubs(g, min_degree=5)
    assert len(hubs) == 1
    hub_node, hub_degree = hubs[0]
    assert hub_node.node_id == "a"
    assert hub_degree == 5


def test_find_hubs_multiple_sorted():
    # hub1: degree 6, hub2: degree 5
    hub1_neighbors = [f"x{i}" for i in range(6)]
    hub2_neighbors = [f"y{i}" for i in range(5)]
    all_nodes = ["hub1", "hub2"] + hub1_neighbors + hub2_neighbors
    all_edges = [("hub1", n) for n in hub1_neighbors] + [("hub2", n) for n in hub2_neighbors]
    g = _graph(*all_nodes, edges=all_edges)

    hubs = find_hubs(g, min_degree=5)
    assert hubs[0][0].node_id == "hub1"
    assert hubs[0][1] == 6
    assert hubs[1][0].node_id == "hub2"
    assert hubs[1][1] == 5


# ── connected_components ───────────────────────────────────────────────────


def test_connected_components_empty():
    g = _graph()
    assert connected_components(g) == ()


def test_connected_components_single_node():
    g = _graph("a")
    comps = connected_components(g)
    assert len(comps) == 1
    assert comps[0][0].node_id == "a"


def test_connected_components_one_component():
    g = _graph("a", "b", "c", edges=[("a", "b"), ("b", "c")])
    comps = connected_components(g)
    assert len(comps) == 1
    ids = {n.node_id for n in comps[0]}
    assert ids == {"a", "b", "c"}


def test_connected_components_two_components():
    g = _graph("a", "b", "c", "d", edges=[("a", "b"), ("c", "d")])
    comps = connected_components(g)
    assert len(comps) == 2
    all_ids = {n.node_id for comp in comps for n in comp}
    assert all_ids == {"a", "b", "c", "d"}


def test_connected_components_isolated_plus_cluster():
    # "orphan" is isolated; a-b-c form cluster
    g = _graph("a", "b", "c", "orphan", edges=[("a", "b"), ("b", "c")])
    comps = connected_components(g)
    assert len(comps) == 2
    sizes = sorted(len(c) for c in comps)
    assert sizes == [1, 3]


# ── neighbors ─────────────────────────────────────────────────────────────


def test_neighbors_unknown_node():
    g = _graph("a", "b", edges=[("a", "b")])
    sub = neighbors(g, "z")
    assert sub.nodes == ()
    assert sub.edges == ()


def test_neighbors_depth_1():
    g = _graph("a", "b", "c", "d", edges=[("a", "b"), ("a", "c"), ("c", "d")])
    sub = neighbors(g, "a", depth=1)
    ids = sub.node_ids()
    # a, b, c included; d is 2 hops away
    assert "a" in ids
    assert "b" in ids
    assert "c" in ids
    assert "d" not in ids


def test_neighbors_depth_2():
    g = _graph("a", "b", "c", "d", edges=[("a", "b"), ("b", "c"), ("c", "d")])
    sub = neighbors(g, "a", depth=2)
    ids = sub.node_ids()
    assert "a" in ids
    assert "b" in ids
    assert "c" in ids
    assert "d" not in ids


def test_neighbors_returns_knowledge_graph():
    g = _graph("a", "b", edges=[("a", "b")])
    sub = neighbors(g, "a", depth=1)
    assert isinstance(sub, KnowledgeGraph)


def test_neighbors_includes_only_internal_edges():
    """Edges in the subgraph must only reference nodes in the subgraph."""
    g = _graph("a", "b", "c", "d", edges=[("a", "b"), ("a", "c"), ("c", "d")])
    sub = neighbors(g, "a", depth=1)
    sub_ids = sub.node_ids()
    for edge in sub.edges:
        assert edge.source_id in sub_ids
        assert edge.target_id in sub_ids


# ── compute_stats ──────────────────────────────────────────────────────────


def test_compute_stats_empty():
    g = KnowledgeGraph(nodes=(), edges=())
    stats = compute_stats(g)
    assert stats.total_nodes == 0
    assert stats.total_edges == 0
    assert stats.orphan_count == 0
    assert stats.component_count == 0


def test_compute_stats_basic():
    nodes = (
        _node("note:1", "note"),
        _node("note:2", "note"),
        _node("bib:1", "bib_entry"),
    )
    edges = (_edge("note:1", "note:2", "link"),)
    g = KnowledgeGraph(nodes=nodes, edges=edges)
    stats = compute_stats(g)

    assert stats.total_nodes == 3
    assert stats.total_edges == 1
    assert stats.orphan_count == 1  # bib:1 is orphan
    assert stats.component_count == 2  # {note:1, note:2} + {bib:1}


def test_compute_stats_nodes_by_type():
    nodes = (
        _node("note:1", "note"),
        _node("note:2", "note"),
        _node("bib:1", "bib_entry"),
        _node("ex:1", "exercise"),
    )
    g = KnowledgeGraph(nodes=nodes, edges=())
    stats = compute_stats(g)

    by_type = dict(stats.nodes_by_type)
    assert by_type["note"] == 2
    assert by_type["bib_entry"] == 1
    assert by_type["exercise"] == 1


def test_compute_stats_edges_by_type():
    nodes = tuple(_node(nid) for nid in ["a", "b", "c", "d"])
    edges = (
        _edge("a", "b", "link"),
        _edge("a", "c", "link"),
        _edge("b", "d", "citation"),
    )
    g = KnowledgeGraph(nodes=nodes, edges=edges)
    stats = compute_stats(g)

    by_type = dict(stats.edges_by_type)
    assert by_type["link"] == 2
    assert by_type["citation"] == 1


def test_compute_stats_returns_graph_stats():
    g = _graph("a")
    stats = compute_stats(g)
    assert isinstance(stats, GraphStats)
