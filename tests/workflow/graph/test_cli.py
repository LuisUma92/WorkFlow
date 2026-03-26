"""Tests for workflow.graph.cli — Click commands via CliRunner."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph
from workflow.graph.cli import graph


# ── Fixtures ───────────────────────────────────────────────────────────────


def _node(nid: str, ntype: str = "note") -> GraphNode:
    return GraphNode(node_id=nid, node_type=ntype, label=f"Label {nid}")


def _edge(src: str, tgt: str, etype: str = "link") -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type=etype)


def _make_kg_with_orphan() -> KnowledgeGraph:
    """Graph with 2 connected nodes + 1 orphan."""
    n1 = _node("note:1", "note")
    n2 = _node("note:2", "note")
    orphan = _node("note:3", "exercise")
    e = _edge("note:1", "note:2", "link")
    return KnowledgeGraph(nodes=(n1, n2, orphan), edges=(e,))


def _make_kg_simple() -> KnowledgeGraph:
    """Graph with 2 connected nodes, no orphans."""
    n1 = _node("note:1", "note")
    n2 = _node("bib:1", "bib_entry")
    e = _edge("note:1", "bib:1", "citation")
    return KnowledgeGraph(nodes=(n1, n2), edges=(e,))


def _make_kg_empty() -> KnowledgeGraph:
    return KnowledgeGraph(nodes=(), edges=())


# ── orphans command ─────────────────────────────────────────────────────────


class TestOrphansCommand:
    def test_orphans_shows_orphan_nodes(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["orphans", "--project", "."])
        assert result.exit_code == 0
        assert "note:3" in result.output
        assert "1 orphan" in result.output

    def test_orphans_empty_shows_message(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["orphans", "--project", "."])
        assert result.exit_code == 0
        assert "No orphaned nodes" in result.output

    def test_orphans_filtered_by_type(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["orphans", "--type", "exercise", "--project", "."])
        assert result.exit_code == 0
        # note:3 is exercise type
        assert "note:3" in result.output

    def test_orphans_type_filter_excludes_other_types(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["orphans", "--type", "note", "--project", "."])
        assert result.exit_code == 0
        # orphan is exercise type, so no note orphans
        assert "No orphaned nodes" in result.output


# ── stats command ───────────────────────────────────────────────────────────


class TestStatsCommand:
    def test_stats_shows_node_count(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["stats", "--project", "."])
        assert result.exit_code == 0
        assert "Nodes: 3" in result.output

    def test_stats_shows_edge_count(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["stats", "--project", "."])
        assert result.exit_code == 0
        assert "Edges: 1" in result.output

    def test_stats_shows_orphan_count(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["stats", "--project", "."])
        assert result.exit_code == 0
        assert "Orphans:" in result.output

    def test_stats_shows_node_types(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["stats", "--project", "."])
        assert result.exit_code == 0
        assert "note" in result.output
        assert "bib_entry" in result.output


# ── export-dot command ──────────────────────────────────────────────────────


class TestExportDotCommand:
    def test_export_dot_to_stdout(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["export-dot", "--project", "."])
        assert result.exit_code == 0
        assert "digraph" in result.output

    def test_export_dot_to_file(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "graph.dot"
            with patch("workflow.graph.cli._build_graph", return_value=kg):
                result = runner.invoke(
                    graph, ["export-dot", "--project", ".", "--output", str(out)]
                )
            assert result.exit_code == 0
            assert out.exists()
            content = out.read_text()
            assert "digraph" in content
            assert "exported to" in result.output

    def test_export_dot_highlight_orphans_flag(self):
        runner = CliRunner()
        kg = _make_kg_with_orphan()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(
                graph, ["export-dot", "--project", ".", "--highlight-orphans"]
            )
        assert result.exit_code == 0
        assert "digraph" in result.output


# ── export-tikz command ─────────────────────────────────────────────────────


class TestExportTikzCommand:
    def test_export_tikz_to_stdout(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(graph, ["export-tikz", "--project", "."])
        assert result.exit_code == 0
        assert "tikzpicture" in result.output

    def test_export_tikz_to_file(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "graph.tex"
            with patch("workflow.graph.cli._build_graph", return_value=kg):
                result = runner.invoke(
                    graph, ["export-tikz", "--project", ".", "--output", str(out)]
                )
            assert result.exit_code == 0
            assert out.exists()
            content = out.read_text()
            assert "tikzpicture" in content

    def test_export_tikz_no_standalone(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(
                graph, ["export-tikz", "--project", ".", "--no-standalone"]
            )
        assert result.exit_code == 0
        assert "documentclass" not in result.output
        assert "tikzpicture" in result.output


# ── clusters command ────────────────────────────────────────────────────────


class TestClustersCommand:
    def test_clusters_no_networkx_shows_install_message(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            with patch(
                "workflow.graph.clustering.detect_communities", return_value=None
            ):
                result = runner.invoke(graph, ["clusters", "--project", "."])
        assert result.exit_code == 0
        assert "networkx" in result.output.lower() or "install" in result.output.lower()

    def test_clusters_empty_graph(self):
        runner = CliRunner()
        kg = _make_kg_empty()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            with patch(
                "workflow.graph.clustering.detect_communities", return_value=()
            ):
                result = runner.invoke(graph, ["clusters", "--project", "."])
        assert result.exit_code == 0
        assert "empty" in result.output.lower() or "No clusters" in result.output

    def test_clusters_shows_communities(self):
        runner = CliRunner()
        n1 = _node("note:1", "note")
        n2 = _node("note:2", "note")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=(_edge("note:1", "note:2"),))
        communities = ((n1, n2),)
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            with patch(
                "workflow.graph.clustering.detect_communities", return_value=communities
            ):
                result = runner.invoke(graph, ["clusters", "--project", "."])
        assert result.exit_code == 0
        assert "Cluster 1" in result.output


# ── neighbors command ───────────────────────────────────────────────────────


class TestNeighborsCommand:
    def test_neighbors_shows_connected_nodes(self):
        runner = CliRunner()
        n1 = _node("note:1", "note")
        n2 = _node("note:2", "note")
        n3 = _node("note:3", "note")
        e1 = _edge("note:1", "note:2")
        e2 = _edge("note:2", "note:3")
        kg = KnowledgeGraph(nodes=(n1, n2, n3), edges=(e1, e2))
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(
                graph, ["neighbors", "note:1", "--depth", "1", "--project", "."]
            )
        assert result.exit_code == 0
        assert "note:1" in result.output
        assert "note:2" in result.output

    def test_neighbors_node_not_found_raises_error(self):
        runner = CliRunner()
        kg = _make_kg_simple()
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(
                graph, ["neighbors", "does_not_exist", "--project", "."]
            )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_neighbors_shows_node_count(self):
        runner = CliRunner()
        n1 = _node("note:1", "note")
        n2 = _node("note:2", "note")
        e = _edge("note:1", "note:2")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=(e,))
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(
                graph, ["neighbors", "note:1", "--project", "."]
            )
        assert result.exit_code == 0
        assert "node" in result.output.lower()

    def test_neighbors_marker_on_query_node(self):
        runner = CliRunner()
        n1 = _node("note:1", "note")
        n2 = _node("note:2", "note")
        e = _edge("note:1", "note:2")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=(e,))
        with patch("workflow.graph.cli._build_graph", return_value=kg):
            result = runner.invoke(
                graph, ["neighbors", "note:1", "--project", "."]
            )
        assert result.exit_code == 0
        # Query node should be marked with *
        assert " *" in result.output
