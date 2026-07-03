"""Tests for orphan lineage root distinction (Wave 3 D3)."""
from __future__ import annotations

import json
from unittest.mock import patch

from click.testing import CliRunner

from workflow.graph.analysis import find_lineage_roots, find_orphans
from workflow.graph.cli import graph
from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(nid: str, ntype: str = "note") -> GraphNode:
    return GraphNode(node_id=nid, node_type=ntype, label=nid)


def _struct_edge(src: str, tgt: str) -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type="note_edge:structural")


def _assoc_edge(src: str, tgt: str) -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type="note_edge:associative")


def _link_edge(src: str, tgt: str) -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type="link")


# ---------------------------------------------------------------------------
# Unit: find_lineage_roots
# ---------------------------------------------------------------------------


def test_find_lineage_roots_basic():
    """A node with outgoing structural edges but no incoming is a lineage root."""
    # leaf → mid → root_actual
    # 'leaf' has outgoing, no incoming structural → it IS a lineage root
    # 'root_actual' has incoming, no outgoing → it is NOT a lineage root
    # 'mid' has both → not a lineage root
    leaf = _node("leaf")
    mid = _node("mid")
    root_actual = _node("root_actual")
    nodes = (leaf, mid, root_actual)
    edges = (
        _struct_edge("leaf", "mid"),
        _struct_edge("mid", "root_actual"),
    )
    kg = KnowledgeGraph(nodes=nodes, edges=edges)

    roots = find_lineage_roots(kg)
    root_ids = {n.node_id for n in roots}
    assert "leaf" in root_ids, "leaf has outgoing but no incoming structural edge"
    assert "mid" not in root_ids, "mid has both incoming and outgoing"
    assert "root_actual" not in root_ids, "root_actual has no outgoing structural edge"


def test_find_lineage_roots_empty_graph():
    kg = KnowledgeGraph(nodes=(), edges=())
    assert find_lineage_roots(kg) == ()


def test_find_lineage_roots_no_structural_edges():
    """When there are no structural edges, no lineage roots exist."""
    n1, n2 = _node("n1"), _node("n2")
    kg = KnowledgeGraph(nodes=(n1, n2), edges=(_link_edge("n1", "n2"),))
    assert find_lineage_roots(kg) == ()


def test_find_lineage_roots_ignores_associative_edges():
    """Associative edges do not count toward lineage root detection."""
    n1, n2 = _node("n1"), _node("n2")
    # n1 has outgoing associative only — not a lineage root
    kg = KnowledgeGraph(nodes=(n1, n2), edges=(_assoc_edge("n1", "n2"),))
    assert find_lineage_roots(kg) == ()


def test_find_lineage_roots_filter_by_type():
    """find_lineage_roots respects node_type filter."""
    leaf_note = _node("leaf_note", "note")
    leaf_bib = _node("leaf_bib", "bib_entry")
    parent = _node("parent", "note")
    kg = KnowledgeGraph(
        nodes=(leaf_note, leaf_bib, parent),
        edges=(
            _struct_edge("leaf_note", "parent"),
            _struct_edge("leaf_bib", "parent"),
        ),
    )
    roots = find_lineage_roots(kg, node_type="note")
    root_ids = {n.node_id for n in roots}
    assert "leaf_note" in root_ids
    assert "leaf_bib" not in root_ids


# ---------------------------------------------------------------------------
# Unit: find_orphans distinguishes lineage roots
# ---------------------------------------------------------------------------


def test_find_orphans_does_not_include_lineage_roots():
    """Lineage roots (with structural edges) are NOT returned by find_orphans."""
    leaf = _node("leaf")
    parent = _node("parent")
    kg = KnowledgeGraph(
        nodes=(leaf, parent),
        edges=(_struct_edge("leaf", "parent"),),
    )
    orphans = find_orphans(kg)
    orphan_ids = {n.node_id for n in orphans}
    assert "leaf" not in orphan_ids, "leaf has structural edge → not a true orphan"
    assert "parent" not in orphan_ids


# ---------------------------------------------------------------------------
# CLI: orphans --json includes is_lineage_root field
# ---------------------------------------------------------------------------


def test_orphans_json_includes_is_lineage_root_false_for_orphans():
    """Orphan nodes in JSON output have is_lineage_root: false."""
    orphan = _node("orphan_node")
    other = _node("connected1")
    other2 = _node("connected2")
    kg = KnowledgeGraph(
        nodes=(orphan, other, other2),
        edges=(_link_edge("connected1", "connected2"),),
    )

    runner = CliRunner()
    with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
        result = runner.invoke(graph, ["orphans", "--json", "--project", "."])

    assert result.exit_code == 0, result.output
    items = json.loads(result.output)
    assert any(isinstance(item, dict) for item in items), "Expected list of dicts"
    # Every item must have is_lineage_root field
    for item in items:
        assert "is_lineage_root" in item, f"Missing is_lineage_root in {item}"
        assert item["is_lineage_root"] is False, "True orphans should have is_lineage_root=False"


def test_orphans_json_includes_lineage_roots_with_flag_true():
    """Nodes with outgoing structural edges but no incoming appear in orphans JSON with is_lineage_root: true."""
    # 'leaf' has outgoing structural but no incoming → lineage root
    # 'root_node' has incoming structural, no outgoing → NOT a lineage root, NOT an orphan
    # 'isolated' has no edges → true orphan
    leaf = _node("leaf_node")
    root_node = _node("root_node")
    isolated = _node("isolated_node")
    kg = KnowledgeGraph(
        nodes=(leaf, root_node, isolated),
        edges=(_struct_edge("leaf_node", "root_node"),),
    )

    runner = CliRunner()
    with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
        result = runner.invoke(graph, ["orphans", "--json", "--project", "."])

    assert result.exit_code == 0, result.output
    items = json.loads(result.output)
    by_id = {item["node_id"]: item for item in items}

    # isolated_node is a true orphan → is_lineage_root=False
    assert "isolated_node" in by_id
    assert by_id["isolated_node"]["is_lineage_root"] is False

    # leaf_node is a lineage root (has outgoing structural, no incoming)
    assert "leaf_node" in by_id
    assert by_id["leaf_node"]["is_lineage_root"] is True

    # root_node has edges → should NOT appear at all
    assert "root_node" not in by_id
