"""Tests for workflow.graph.tikz_export."""
from __future__ import annotations
import pytest

from workflow.graph.domain import GraphNode, GraphEdge, KnowledgeGraph
from workflow.graph.tikz_export import spring_layout, graph_to_tikz


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


def _two_node_graph() -> KnowledgeGraph:
    n1 = GraphNode(node_id="note:1", node_type="note", label="intro.tex")
    n2 = GraphNode(node_id="bib:serway", node_type="bib_entry", label="serway2019")
    e = GraphEdge(source_id="note:1", target_id="bib:serway", edge_type="cites")
    return KnowledgeGraph(nodes=(n1, n2), edges=(e,))


# ---------------------------------------------------------------------------
# spring_layout tests
# ---------------------------------------------------------------------------
class TestSpringLayout:
    def test_spring_layout_deterministic(self):
        g = _make_graph(4, 3)
        result1 = spring_layout(g, seed=42)
        result2 = spring_layout(g, seed=42)
        for ln1, ln2 in zip(result1, result2):
            assert abs(ln1.x - ln2.x) < 1e-9
            assert abs(ln1.y - ln2.y) < 1e-9

    def test_different_seeds_different_layout(self):
        g = _make_graph(4, 3)
        result1 = spring_layout(g, seed=42)
        result2 = spring_layout(g, seed=99)
        positions_same = all(
            abs(ln1.x - ln2.x) < 1e-6 and abs(ln1.y - ln2.y) < 1e-6
            for ln1, ln2 in zip(result1, result2)
        )
        assert not positions_same

    def test_spring_layout_all_nodes(self):
        g = _make_graph(5, 4)
        layout = spring_layout(g)
        assert len(layout) == 5
        node_ids = {ln.node.node_id for ln in layout}
        expected = {f"note:{i}" for i in range(5)}
        assert node_ids == expected

    def test_spring_layout_empty_graph(self):
        layout = spring_layout(_empty_graph())
        assert len(layout) == 0

    def test_spring_layout_single_node(self):
        g = KnowledgeGraph(
            nodes=(GraphNode(node_id="n:1", node_type="note", label="Solo"),),
            edges=(),
        )
        layout = spring_layout(g)
        assert len(layout) == 1

    def test_spring_layout_within_bounds(self):
        g = _make_graph(6, 4)
        layout = spring_layout(g, width=10.0, height=8.0)
        for ln in layout:
            assert 0.0 <= ln.x <= 10.0, f"x={ln.x} out of [0, 10]"
            assert 0.0 <= ln.y <= 8.0, f"y={ln.y} out of [0, 8]"

    def test_layout_node_contains_graph_node(self):
        g = _make_graph(2, 1)
        layout = spring_layout(g)
        for ln in layout:
            assert hasattr(ln, "node")
            assert hasattr(ln, "x")
            assert hasattr(ln, "y")


# ---------------------------------------------------------------------------
# graph_to_tikz tests
# ---------------------------------------------------------------------------
class TestGraphToTikz:
    def test_empty_graph_tikz(self):
        result = graph_to_tikz(_empty_graph())
        assert "tikzpicture" in result

    def test_standalone_wrapping(self):
        result = graph_to_tikz(_empty_graph(), standalone=True)
        assert r"\documentclass" in result
        assert r"\begin{document}" in result
        assert r"\end{document}" in result

    def test_no_standalone(self):
        result = graph_to_tikz(_empty_graph(), standalone=False)
        assert r"\documentclass" not in result

    def test_tikz_nodes_positioned(self):
        result = graph_to_tikz(_two_node_graph(), standalone=False)
        assert r"\node" in result
        assert "at (" in result

    def test_tikz_edges_drawn(self):
        result = graph_to_tikz(_two_node_graph(), standalone=False)
        assert r"\draw" in result
        assert "->" in result

    def test_tikz_node_labels_in_output(self):
        result = graph_to_tikz(_two_node_graph(), standalone=False)
        assert "intro.tex" in result
        assert "serway2019" in result

    def test_tikz_custom_layout(self):
        """Providing a pre-computed layout is used instead of recomputing."""
        g = _two_node_graph()
        layout = spring_layout(g, seed=1)
        result1 = graph_to_tikz(g, layout=layout, standalone=False)
        result2 = graph_to_tikz(g, layout=layout, standalone=False)
        assert result1 == result2

    def test_tikz_title_in_output(self):
        result = graph_to_tikz(_empty_graph(), title="My Diagram", standalone=False)
        assert "My Diagram" in result

    def test_standalone_contains_tikzpicture(self):
        result = graph_to_tikz(_make_graph(2, 1), standalone=True)
        assert r"\begin{tikzpicture}" in result
        assert r"\end{tikzpicture}" in result

    def test_node_colors_applied(self):
        g = KnowledgeGraph(
            nodes=(GraphNode(node_id="n:1", node_type="note", label="Note"),),
            edges=(),
        )
        result = graph_to_tikz(g, standalone=False, node_colors={"note": "cyan!60"})
        assert "cyan" in result

    def test_multiple_edges(self):
        g = _make_graph(3, 2)
        result = graph_to_tikz(g, standalone=False)
        draw_count = result.count(r"\draw")
        assert draw_count >= 2
