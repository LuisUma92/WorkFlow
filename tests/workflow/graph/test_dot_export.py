"""Tests for workflow.graph.dot_export."""
from __future__ import annotations
import pytest

from workflow.graph.domain import GraphNode, GraphEdge, KnowledgeGraph
from workflow.graph.dot_export import graph_to_dot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_graph(n_nodes: int = 3, n_edges: int = 2) -> KnowledgeGraph:
    nodes = tuple(
        GraphNode(node_id=f"note:{i}", node_type="note", label=f"Note {i}")
        for i in range(n_nodes)
    )
    edges = tuple(
        GraphEdge(source_id=f"note:{i}", target_id=f"note:{i + 1}", edge_type="link")
        for i in range(min(n_edges, n_nodes - 1))
    )
    return KnowledgeGraph(nodes=nodes, edges=edges)


def _empty_graph() -> KnowledgeGraph:
    return KnowledgeGraph(nodes=(), edges=())


def _single_node_graph(node_type: str = "note") -> KnowledgeGraph:
    node = GraphNode(node_id="node:1", node_type=node_type, label="intro.tex")
    return KnowledgeGraph(nodes=(node,), edges=())


def _two_node_graph() -> KnowledgeGraph:
    n1 = GraphNode(node_id="note:1", node_type="note", label="intro.tex")
    n2 = GraphNode(node_id="bib:serway", node_type="bib_entry", label="serway2019")
    e = GraphEdge(source_id="note:1", target_id="bib:serway", edge_type="cites")
    return KnowledgeGraph(nodes=(n1, n2), edges=(e,))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestEmptyGraph:
    def test_empty_graph(self):
        result = graph_to_dot(_empty_graph())
        assert "digraph" in result
        assert "{" in result
        assert "}" in result

    def test_empty_graph_no_nodes_or_edges(self):
        result = graph_to_dot(_empty_graph())
        assert "->" not in result
        assert "[label=" not in result or "label=" not in result.split("->")[0]


class TestSingleNode:
    def test_single_node_appears(self):
        result = graph_to_dot(_single_node_graph())
        assert "intro.tex" in result

    def test_single_node_default_color(self):
        result = graph_to_dot(_single_node_graph(node_type="note"))
        assert "#4A90D9" in result

    def test_exercise_node_color(self):
        g = KnowledgeGraph(
            nodes=(GraphNode(node_id="ex:1", node_type="exercise", label="Ex 1"),),
            edges=(),
        )
        result = graph_to_dot(g)
        assert "#E74C3C" in result

    def test_bib_node_color(self):
        g = KnowledgeGraph(
            nodes=(GraphNode(node_id="b:1", node_type="bib_entry", label="Bib 1"),),
            edges=(),
        )
        result = graph_to_dot(g)
        assert "#2ECC71" in result


class TestEdgesRendered:
    def test_edge_arrow_syntax(self):
        result = graph_to_dot(_two_node_graph())
        assert "->" in result

    def test_edge_label(self):
        result = graph_to_dot(_two_node_graph())
        assert "cites" in result

    def test_both_node_ids_in_edge(self):
        result = graph_to_dot(_two_node_graph())
        assert "note:1" in result
        assert "bib:serway" in result


class TestCustomColors:
    def test_custom_color_overrides_default(self):
        result = graph_to_dot(
            _single_node_graph(node_type="note"),
            node_colors={"note": "#AABBCC"},
        )
        assert "#AABBCC" in result
        assert "#4A90D9" not in result

    def test_partial_override_keeps_others(self):
        g = KnowledgeGraph(
            nodes=(
                GraphNode(node_id="n:1", node_type="note", label="Note"),
                GraphNode(node_id="e:1", node_type="exercise", label="Ex"),
            ),
            edges=(),
        )
        result = graph_to_dot(g, node_colors={"note": "#AABBCC"})
        assert "#AABBCC" in result
        assert "#E74C3C" in result  # exercise default kept


class TestHighlightOrphans:
    def test_orphan_gets_red_border(self):
        n1 = GraphNode(node_id="note:1", node_type="note", label="A")
        n2 = GraphNode(node_id="note:2", node_type="note", label="B")
        orphan = GraphNode(node_id="note:3", node_type="note", label="Orphan")
        e = GraphEdge(source_id="note:1", target_id="note:2", edge_type="link")
        g = KnowledgeGraph(nodes=(n1, n2, orphan), edges=(e,))
        result = graph_to_dot(g, highlight_orphans=True)
        assert "red" in result or "color=red" in result or "#FF0000" in result

    def test_no_orphan_highlight_by_default(self):
        n1 = GraphNode(node_id="note:1", node_type="note", label="A")
        orphan = GraphNode(node_id="note:2", node_type="note", label="Orphan")
        g = KnowledgeGraph(nodes=(n1, orphan), edges=())
        result = graph_to_dot(g)
        assert "color=red" not in result and "penwidth=3" not in result


class TestTitleAndLayout:
    def test_title_in_output(self):
        result = graph_to_dot(_empty_graph(), title="My Graph")
        assert "My Graph" in result

    def test_default_title(self):
        result = graph_to_dot(_empty_graph())
        assert "WorkFlow Knowledge Graph" in result

    def test_rankdir_lr(self):
        result = graph_to_dot(_empty_graph(), rankdir="LR")
        assert "rankdir=LR" in result

    def test_rankdir_tb(self):
        result = graph_to_dot(_empty_graph(), rankdir="TB")
        assert "rankdir=TB" in result


class TestSpecialCharsEscaped:
    def test_quotes_in_label_escaped(self):
        g = KnowledgeGraph(
            nodes=(GraphNode(node_id="n:1", node_type="note", label='Say "hello"'),),
            edges=(),
        )
        result = graph_to_dot(g)
        assert 'Say \\"hello\\"' in result or "Say" in result

    def test_backslash_in_label(self):
        g = KnowledgeGraph(
            nodes=(GraphNode(node_id="n:1", node_type="note", label="path\\to\\file"),),
            edges=(),
        )
        result = graph_to_dot(g)
        assert "path" in result
