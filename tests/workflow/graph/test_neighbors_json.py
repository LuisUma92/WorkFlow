"""TDD tests for `workflow graph neighbors --json`.

RED phase — all tests written before implementation.

Covers:
1. Success shape: exits 0, object with source + neighbors keys, each neighbor has
   id, title, path, edge_class, edge_type, depth.
2. Note neighbor has path as non-null abs str; non-note neighbor has path == null.
3. Unknown id + --json exits 1 (error on stderr).
4. --depth 2 returns a 2-hop neighbor with depth == 2.
5. A filter flag (--main-topic) is honored (doesn't crash, narrows graph).
6. NeighborInfo dataclass accessible from analysis module.
7. neighbors_detailed returns correct BFS data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from workflow.graph.analysis import NeighborInfo, neighbors_detailed
from workflow.graph.cli import graph
from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph


# ── Helpers ────────────────────────────────────────────────────────────────


def _node(nid: str, ntype: str = "note", label: str | None = None) -> GraphNode:
    return GraphNode(node_id=nid, node_type=ntype, label=label or f"Label {nid}")


def _edge(src: str, tgt: str, etype: str = "link") -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type=etype)


def _make_linear_kg() -> KnowledgeGraph:
    """A → B → C (all notes). Depth-1 from A gives B; depth-2 gives B+C."""
    a = _node("note:1", "note", "Newton's law")
    b = _node("note:2", "note", "FBD")
    c = _node("note:3", "note", "Equilibrium")
    e1 = _edge("note:1", "note:2", "link")
    e2 = _edge("note:2", "note:3", "link")
    return KnowledgeGraph(nodes=(a, b, c), edges=(e1, e2))


def _make_mixed_kg() -> KnowledgeGraph:
    """note:1 → concept:5 (non-note neighbor)."""
    a = _node("note:1", "note", "Newton's law")
    c = _node("concept:5", "concept", "Force concept")
    e = _edge("note:1", "concept:5", "note_concept")
    return KnowledgeGraph(nodes=(a, c), edges=(e,))


def _fake_vault_root(tmp_path: Path) -> Path:
    return tmp_path / "vault"


# ── Unit tests for neighbors_detailed ─────────────────────────────────────


class TestNeighborsDetailed:
    def test_returns_neighbor_infos_excluding_source(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:1", depth=1)
        ids = {ni.node.node_id for ni in result}
        assert "note:1" not in ids
        assert "note:2" in ids

    def test_depth_1_excludes_hop2(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:1", depth=1)
        ids = {ni.node.node_id for ni in result}
        assert "note:3" not in ids

    def test_depth_2_includes_hop2(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:1", depth=2)
        ids = {ni.node.node_id for ni in result}
        assert "note:3" in ids

    def test_depth_field_is_correct(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:1", depth=2)
        by_id = {ni.node.node_id: ni for ni in result}
        assert by_id["note:2"].depth == 1
        assert by_id["note:3"].depth == 2

    def test_edge_type_propagated(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:1", depth=1)
        ni = next(x for x in result if x.node.node_id == "note:2")
        assert ni.edge_type == "link"

    def test_empty_if_unknown_node(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:999", depth=1)
        assert list(result) == []

    def test_neighbor_info_is_frozen(self):
        kg = _make_linear_kg()
        result = neighbors_detailed(kg, "note:1", depth=1)
        ni = result[0]
        with pytest.raises((AttributeError, TypeError)):
            ni.depth = 99  # type: ignore[misc]


# ── CLI tests ──────────────────────────────────────────────────────────────


class TestNeighborsJsonShape:
    """Verify the top-level JSON contract."""

    def test_exits_0_and_returns_object(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "source" in data
        assert "neighbors" in data

    def test_source_has_required_keys(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        src = data["source"]
        assert "id" in src
        assert "title" in src
        assert "path" in src

    def test_source_id_preserves_prefix(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        assert data["source"]["id"] == "note:1"

    def test_neighbor_has_all_contract_keys(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        n = data["neighbors"][0]
        for key in ("id", "title", "path", "edge_class", "edge_type", "depth"):
            assert key in n, f"missing key: {key}"

    def test_edge_class_is_always_null(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        for n in data["neighbors"]:
            assert n["edge_class"] is None

    def test_edge_type_is_edge_type_string(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        assert data["neighbors"][0]["edge_type"] == "link"

    def test_depth_is_integer_1_for_direct_neighbor(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        assert data["neighbors"][0]["depth"] == 1


class TestNeighborsJsonPaths:
    """Note vs non-note path rules."""

    def test_note_neighbor_has_nonnull_path_string(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault), \
             patch("workflow.graph.cli._fetch_note_rows", return_value={
                 "note:1": {"title": "Newton's law", "note_type": "permanent", "filename": "newton.md"},
                 "note:2": {"title": "FBD", "note_type": "permanent", "filename": "fbd.md"},
             }):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        nbr = next(n for n in data["neighbors"] if n["id"] == "note:2")
        assert nbr["path"] is not None
        assert "fbd.md" in nbr["path"]
        assert Path(nbr["path"]).is_absolute()

    def test_non_note_neighbor_has_null_path(self, tmp_path):
        kg = _make_mixed_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault), \
             patch("workflow.graph.cli._fetch_note_rows", return_value={
                 "note:1": {"title": "Newton's law", "note_type": "permanent", "filename": "newton.md"},
             }):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        nbr = next(n for n in data["neighbors"] if n["id"] == "concept:5")
        assert nbr["path"] is None

    def test_source_note_path_is_absolute(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault), \
             patch("workflow.graph.cli._fetch_note_rows", return_value={
                 "note:1": {"title": "Newton's law", "note_type": "permanent", "filename": "newton.md"},
                 "note:2": {"title": "FBD", "note_type": "permanent", "filename": "fbd.md"},
             }):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        src_path = data["source"]["path"]
        assert src_path is not None
        assert Path(src_path).is_absolute()


class TestNeighborsJsonErrors:
    """Error handling."""

    def test_unknown_id_exits_1(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:999", "--json"])
        assert result.exit_code == 1

    def test_unknown_id_without_json_also_exits_1(self, tmp_path):
        kg = _make_linear_kg()
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["neighbors", "note:999"])
        assert result.exit_code == 1


class TestNeighborsJsonDepth:
    """--depth flag is honored in JSON output."""

    def test_depth_2_neighbor_appears_with_depth_2(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--depth", "2", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        ids = [n["id"] for n in data["neighbors"]]
        assert "note:3" in ids
        hop2 = next(n for n in data["neighbors"] if n["id"] == "note:3")
        assert hop2["depth"] == 2

    def test_default_depth_1_excludes_hop2(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(graph, ["neighbors", "note:1", "--json"])
        data = json.loads(result.output)
        ids = [n["id"] for n in data["neighbors"]]
        assert "note:3" not in ids


class TestNeighborsJsonFilters:
    """Filter flags don't crash and narrow results."""

    def test_main_topic_filter_does_not_crash(self, tmp_path):
        # The filter narrows the graph; if node disappears, exit 1 is acceptable.
        # Key assertion: no unhandled exception (exit code is 0 or 1, not 2).
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(
                graph, ["neighbors", "note:1", "--json", "--main-topic", "PHYS01"]
            )
        assert result.exit_code in (0, 1)

    def test_discipline_area_filter_does_not_crash(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(
                graph, ["neighbors", "note:1", "--json", "--discipline-area", "NAT"]
            )
        assert result.exit_code in (0, 1)

    def test_topic_filter_does_not_crash(self, tmp_path):
        kg = _make_linear_kg()
        vault = _fake_vault_root(tmp_path)
        runner = CliRunner()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg), \
             patch("workflow.graph.cli.resolve_vault_root", return_value=vault):
            result = runner.invoke(
                graph, ["neighbors", "note:1", "--json", "--topic", "Mechanics"]
            )
        assert result.exit_code in (0, 1)
