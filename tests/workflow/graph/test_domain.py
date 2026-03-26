"""Tests for workflow.graph.domain — GraphNode, GraphEdge, KnowledgeGraph."""
from __future__ import annotations

import pytest

from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph


# ── GraphNode ──────────────────────────────────────────────────────────────


def test_graph_node_creation():
    node = GraphNode(node_id="note:1", node_type="note", label="my-note.md")
    assert node.node_id == "note:1"
    assert node.node_type == "note"
    assert node.label == "my-note.md"


def test_graph_node_immutable():
    node = GraphNode(node_id="note:1", node_type="note", label="x")
    with pytest.raises((AttributeError, TypeError)):
        node.node_id = "note:2"  # type: ignore[misc]


def test_graph_node_hashable():
    node1 = GraphNode(node_id="note:1", node_type="note", label="x")
    node2 = GraphNode(node_id="note:1", node_type="note", label="x")
    assert node1 == node2
    assert hash(node1) == hash(node2)
    s = {node1, node2}
    assert len(s) == 1


# ── GraphEdge ──────────────────────────────────────────────────────────────


def test_graph_edge_creation():
    edge = GraphEdge(source_id="note:1", target_id="note:2", edge_type="link")
    assert edge.source_id == "note:1"
    assert edge.target_id == "note:2"
    assert edge.edge_type == "link"
    assert edge.label == ""


def test_graph_edge_with_label():
    edge = GraphEdge(
        source_id="note:1", target_id="bib:42", edge_type="citation", label="Smith2020"
    )
    assert edge.label == "Smith2020"


def test_graph_edge_immutable():
    edge = GraphEdge(source_id="a", target_id="b", edge_type="link")
    with pytest.raises((AttributeError, TypeError)):
        edge.source_id = "c"  # type: ignore[misc]


def test_graph_edge_hashable():
    e1 = GraphEdge(source_id="a", target_id="b", edge_type="link")
    e2 = GraphEdge(source_id="a", target_id="b", edge_type="link")
    assert e1 == e2
    assert hash(e1) == hash(e2)


# ── KnowledgeGraph ─────────────────────────────────────────────────────────


def _make_simple_graph() -> KnowledgeGraph:
    nodes = (
        GraphNode("note:1", "note", "a.md"),
        GraphNode("note:2", "note", "b.md"),
        GraphNode("bib:10", "bib_entry", "Smith2020"),
    )
    edges = (
        GraphEdge("note:1", "note:2", "link"),
        GraphEdge("note:1", "bib:10", "citation"),
    )
    return KnowledgeGraph(nodes=nodes, edges=edges)


def test_knowledge_graph_immutable():
    g = _make_simple_graph()
    with pytest.raises((AttributeError, TypeError)):
        g.nodes = ()  # type: ignore[misc]


def test_node_ids():
    g = _make_simple_graph()
    ids = g.node_ids()
    assert isinstance(ids, frozenset)
    assert ids == {"note:1", "note:2", "bib:10"}


def test_adjacency_structure():
    g = _make_simple_graph()
    adj = g.adjacency()
    # All node_ids present as keys
    assert set(adj.keys()) == {"note:1", "note:2", "bib:10"}
    # note:1 connects to note:2 and bib:10
    assert set(adj["note:1"]) == {"note:2", "bib:10"}
    # note:2 connects back to note:1 (undirected)
    assert "note:1" in adj["note:2"]
    # bib:10 connects back to note:1
    assert "note:1" in adj["bib:10"]


def test_adjacency_empty_graph():
    g = KnowledgeGraph(nodes=(), edges=())
    adj = g.adjacency()
    assert adj == {}


def test_knowledge_graph_stores_tuples():
    g = _make_simple_graph()
    assert isinstance(g.nodes, tuple)
    assert isinstance(g.edges, tuple)
    assert len(g.nodes) == 3
    assert len(g.edges) == 2
