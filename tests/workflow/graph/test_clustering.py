"""Tests for workflow.graph.clustering — community detection."""
from __future__ import annotations

import sys
import types
import unittest.mock as mock

import pytest

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


# ── Tests ──────────────────────────────────────────────────────────────────


class TestDetectCommunitiesWithoutNetworkx:
    """detect_communities returns None when networkx is not installed."""

    def test_returns_none_on_import_error(self, monkeypatch):
        # Remove networkx from sys.modules and make it unimportable
        monkeypatch.setitem(sys.modules, "networkx", None)  # type: ignore[arg-type]
        # Re-import the module after patching
        import importlib
        import workflow.graph.clustering as clustering_mod
        importlib.reload(clustering_mod)

        kg = _graph("a", "b", edges=[("a", "b")])
        result = clustering_mod.detect_communities(kg)
        assert result is None


class TestDetectCommunitiesEmptyGraph:
    """detect_communities returns empty tuple for an empty graph."""

    def test_empty_graph_returns_empty_tuple(self):
        pytest.importorskip("networkx")
        from workflow.graph.clustering import detect_communities

        kg = KnowledgeGraph(nodes=(), edges=())
        result = detect_communities(kg)
        assert result == ()

    def test_nodes_only_no_edges(self):
        pytest.importorskip("networkx")
        from workflow.graph.clustering import detect_communities

        kg = _graph("a", "b", "c")
        result = detect_communities(kg)
        # 3 isolated nodes → 3 singleton communities
        assert result is not None
        assert len(result) == 3


networkx_available = pytest.mark.skipif(
    pytest.importorskip("networkx", reason="networkx not installed") is None,
    reason="networkx not installed",
)


class TestDetectCommunitiesWithData:
    """detect_communities returns correct communities when networkx is available."""

    def test_two_dense_clusters(self):
        pytest.importorskip("networkx")
        from workflow.graph.clustering import detect_communities

        # Cluster 1: a-b-c fully connected
        # Cluster 2: x-y-z fully connected
        # One weak bridge: c-x
        kg = _graph(
            "a", "b", "c", "x", "y", "z",
            edges=[
                ("a", "b"), ("b", "c"), ("a", "c"),
                ("x", "y"), ("y", "z"), ("x", "z"),
                ("c", "x"),
            ],
        )
        result = detect_communities(kg)
        assert result is not None
        # We get at least 1 community
        assert len(result) >= 1
        # All nodes appear in some community
        all_nids = {n.node_id for community in result for n in community}
        assert all_nids == {"a", "b", "c", "x", "y", "z"}

    def test_returns_graph_nodes_not_strings(self):
        pytest.importorskip("networkx")
        from workflow.graph.clustering import detect_communities

        kg = _graph("n1", "n2", edges=[("n1", "n2")])
        result = detect_communities(kg)
        assert result is not None
        for community in result:
            for node in community:
                assert isinstance(node, GraphNode)

    def test_community_tuple_structure(self):
        pytest.importorskip("networkx")
        from workflow.graph.clustering import detect_communities

        kg = _graph("a", "b", edges=[("a", "b")])
        result = detect_communities(kg)
        assert result is not None
        assert isinstance(result, tuple)
        for community in result:
            assert isinstance(community, tuple)
