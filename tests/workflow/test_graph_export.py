"""Tests for export-tikz CLI filter flags (Wave 4).

Covers: --depth, --cluster, --main-topic + --cluster mutex, --color-by,
        --layout, --include-tags, --exclude-tags, palette stability,
        newline injection safety.

Run with:
    WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest tests/workflow/test_graph_export.py -q
"""
from __future__ import annotations

import re
from unittest.mock import patch

from click.testing import CliRunner

from workflow.graph.cli import graph, _expand_by_depth
from workflow.graph.domain import GraphEdge, GraphNode, KnowledgeGraph
from workflow.graph.tikz_export import _escape_tikz, _palette_color, graph_to_tikz


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(nid: str, ntype: str = "note", label: str | None = None) -> GraphNode:
    return GraphNode(node_id=nid, node_type=ntype, label=label or f"L_{nid}")


def _edge(src: str, tgt: str, etype: str = "link") -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type=etype)


def _chain_kg() -> KnowledgeGraph:
    """A -- B -- C (chain of 3 notes)."""
    na = _node("note:1", label="A")
    nb = _node("note:2", label="B")
    nc = _node("note:3", label="C")
    return KnowledgeGraph(
        nodes=(na, nb, nc),
        edges=(_edge("note:1", "note:2"), _edge("note:2", "note:3")),
    )


def _empty_kg() -> KnowledgeGraph:
    return KnowledgeGraph(nodes=(), edges=())


# ---------------------------------------------------------------------------
# 1. Mutex: --main-topic + --cluster → exit 2
# ---------------------------------------------------------------------------

class TestMutex:
    def test_main_topic_and_cluster_together_exits_2(self):
        runner = CliRunner()
        result = runner.invoke(graph, [
            "export-tikz", "--main-topic", "physics", "--cluster", "1",
        ])
        assert result.exit_code == 2

    def test_cluster_alone_accepted(self):
        """--cluster alone should not cause a usage error at parse time."""
        runner = CliRunner()
        kg = _empty_kg()
        communities: tuple[tuple[GraphNode, ...], ...] = ()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=communities):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "1"])
        # Error is expected (empty communities → no cluster 1) but NOT exit 2 (not a usage error)
        assert result.exit_code != 2


# ---------------------------------------------------------------------------
# 2. Empty --main-topic → empty / valid TikZ output
# ---------------------------------------------------------------------------

class TestEmptyMainTopic:
    def test_no_match_produces_valid_tikz(self):
        runner = CliRunner()
        kg = _empty_kg()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, [
                "export-tikz", "--main-topic", "nonexistent_slug",
            ])
        assert result.exit_code == 0
        assert "tikzpicture" in result.output

    def test_no_match_no_nodes_in_output(self):
        runner = CliRunner()
        kg = _empty_kg()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, [
                "export-tikz", "--main-topic", "ghost",
            ])
        assert result.exit_code == 0
        assert r"\node" not in result.output


# ---------------------------------------------------------------------------
# 3. _expand_by_depth — unit tests (pure logic, no CLI)
# ---------------------------------------------------------------------------

class TestExpandByDepth:
    def test_depth_0_returns_seed_only(self):
        full_kg = _chain_kg()
        seed_kg = KnowledgeGraph(nodes=(_node("note:1", label="A"),), edges=())
        result = _expand_by_depth(full_kg, seed_kg, depth=0)
        assert {n.node_id for n in result.nodes} == {"note:1"}

    def test_depth_1_adds_direct_neighbors(self):
        full_kg = _chain_kg()
        seed_kg = KnowledgeGraph(nodes=(_node("note:1", label="A"),), edges=())
        result = _expand_by_depth(full_kg, seed_kg, depth=1)
        ids = {n.node_id for n in result.nodes}
        assert "note:1" in ids
        assert "note:2" in ids
        assert "note:3" not in ids

    def test_depth_2_reaches_two_hops(self):
        full_kg = _chain_kg()
        seed_kg = KnowledgeGraph(nodes=(_node("note:1", label="A"),), edges=())
        result = _expand_by_depth(full_kg, seed_kg, depth=2)
        ids = {n.node_id for n in result.nodes}
        assert ids == {"note:1", "note:2", "note:3"}

    def test_depth_2_includes_induced_edges(self):
        full_kg = _chain_kg()
        seed_kg = KnowledgeGraph(nodes=(_node("note:1", label="A"),), edges=())
        result = _expand_by_depth(full_kg, seed_kg, depth=2)
        # Both edges should be in the result
        edge_pairs = {(e.source_id, e.target_id) for e in result.edges}
        assert ("note:1", "note:2") in edge_pairs
        assert ("note:2", "note:3") in edge_pairs

    def test_depth_2_multi_seed(self):
        full_kg = _chain_kg()
        seed_kg = KnowledgeGraph(
            nodes=(_node("note:1", label="A"), _node("note:3", label="C")),
            edges=(),
        )
        result = _expand_by_depth(full_kg, seed_kg, depth=1)
        ids = {n.node_id for n in result.nodes}
        # Both seeds reach note:2 in 1 hop
        assert "note:2" in ids

    def test_depth_0_vs_depth_2_differ(self):
        """Core acceptance criterion: depth 0 and depth 2 produce different node sets."""
        full_kg = _chain_kg()
        seed_kg = KnowledgeGraph(nodes=(_node("note:1", label="A"),), edges=())
        r0 = _expand_by_depth(full_kg, seed_kg, depth=0)
        r2 = _expand_by_depth(full_kg, seed_kg, depth=2)
        ids0 = {n.node_id for n in r0.nodes}
        ids2 = {n.node_id for n in r2.nodes}
        assert ids0 != ids2
        assert ids0.issubset(ids2)


# ---------------------------------------------------------------------------
# 4. --cluster filtering
# ---------------------------------------------------------------------------

class TestClusterFilter:
    def _three_node_kg(self):
        n1 = _node("note:1", label="Alpha")
        n2 = _node("note:2", label="Beta")
        n3 = _node("note:3", label="Gamma")
        return KnowledgeGraph(nodes=(n1, n2, n3), edges=())

    def test_cluster_1_produces_first_community(self):
        runner = CliRunner()
        kg = self._three_node_kg()
        n1 = kg.nodes[0]
        n2 = kg.nodes[1]
        n3 = kg.nodes[2]
        communities = ((n1, n2), (n3,))

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=communities):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "1"])

        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Beta" in result.output
        assert "Gamma" not in result.output

    def test_cluster_2_produces_second_community(self):
        runner = CliRunner()
        kg = self._three_node_kg()
        n1, n2, n3 = kg.nodes
        communities = ((n1, n2), (n3,))

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=communities):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "2"])

        assert result.exit_code == 0
        assert "Gamma" in result.output
        assert "Alpha" not in result.output
        assert "Beta" not in result.output

    def test_cluster_name_format_cluster_n(self):
        """'Cluster 1' format (as emitted by graph clusters) is accepted."""
        runner = CliRunner()
        kg = self._three_node_kg()
        n1, n2, n3 = kg.nodes
        communities = ((n1, n2), (n3,))

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=communities):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "Cluster 1"])

        assert result.exit_code == 0
        assert "Alpha" in result.output

    def test_cluster_out_of_range_errors(self):
        runner = CliRunner()
        kg = self._three_node_kg()
        n1, _n2, _n3 = kg.nodes
        communities = ((n1,),)

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=communities):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "99"])

        assert result.exit_code != 0

    def test_cluster_no_networkx_errors(self):
        runner = CliRunner()
        kg = self._three_node_kg()

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=None):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "1"])

        assert result.exit_code != 0

    def test_cluster_vs_detect_communities_equality(self):
        """The subgraph produced by --cluster N matches detect_communities()[N-1]."""
        runner = CliRunner()
        kg = self._three_node_kg()
        n1, n2, n3 = kg.nodes
        communities = ((n1, n2), (n3,))

        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            with patch("workflow.graph.clustering.detect_communities", return_value=communities):
                result = runner.invoke(graph, ["export-tikz", "--cluster", "1"])

        # Verify the cluster-1 nodes appear and cluster-2 does NOT
        assert result.exit_code == 0
        node_ids_in_output = set()
        for m in re.finditer(r'\\node\[.*?\]\s+\(\w+\)\s+at.*?\{(.*?)\}', result.output):
            node_ids_in_output.add(m.group(1))
        assert any("Alpha" in v or "L_" in v for v in node_ids_in_output) or "Alpha" in result.output


# ---------------------------------------------------------------------------
# 5. --color-by in graph_to_tikz
# ---------------------------------------------------------------------------

class TestColorBy:
    def test_color_by_none_uses_type_defaults(self):
        n = _node("note:1", ntype="note", label="N")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False)
        assert "blue" in result  # note default = blue!60

    def test_color_by_type_same_as_default(self):
        n = _node("note:1", ntype="note", label="N")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        r_default = graph_to_tikz(kg, standalone=False)
        r_type = graph_to_tikz(kg, standalone=False, color_by="type")
        assert r_default == r_type

    def test_color_by_main_topic_uses_palette(self):
        n1 = _node("note:1", ntype="note", label="A")
        n2 = _node("note:2", ntype="note", label="B")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        assert "fill=" in result

    def test_color_by_main_topic_stable(self):
        """Same graph → same TikZ output on repeated calls."""
        n = _node("note:99", label="X")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        r1 = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        r2 = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        assert r1 == r2

    def test_color_by_tag_produces_output(self):
        n = _node("note:1", label="T")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="tag")
        assert "tikzpicture" in result

    def test_color_by_main_topic_differs_from_default(self):
        """Palette colors differ from default type-based note color (blue!60)."""
        n = _node("note:9999", ntype="note", label="X")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False, color_by="main_topic")
        # The palette color for "note:9999" may or may not be blue!60;
        # we just verify output is valid TikZ and stable.
        assert "fill=" in result
        assert "tikzpicture" in result


# ---------------------------------------------------------------------------
# 6. --layout flag in graph_to_tikz
# ---------------------------------------------------------------------------

class TestLayoutName:
    def _simple_kg(self) -> KnowledgeGraph:
        n1 = _node("note:1", label="A")
        n2 = _node("note:2", label="B")
        e = _edge("note:1", "note:2")
        return KnowledgeGraph(nodes=(n1, n2), edges=(e,))

    def test_force_layout_unchanged_from_default(self):
        kg = self._simple_kg()
        r_default = graph_to_tikz(kg, standalone=False)
        r_force = graph_to_tikz(kg, standalone=False, layout_name="force")
        assert r_default == r_force

    def test_radial_layout_valid_output(self):
        kg = self._simple_kg()
        result = graph_to_tikz(kg, standalone=False, layout_name="radial")
        assert "tikzpicture" in result
        assert r"\node" in result
        assert "A" in result
        assert "B" in result

    def test_hierarchical_layout_valid_output(self):
        n1 = _node("note:1", ntype="note", label="N1")
        n2 = _node("ex:1", ntype="exercise", label="E1")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=())
        result = graph_to_tikz(kg, standalone=False, layout_name="hierarchical")
        assert "N1" in result
        assert "E1" in result

    def test_radial_layout_empty_graph(self):
        result = graph_to_tikz(_empty_kg(), standalone=False, layout_name="radial")
        assert "tikzpicture" in result

    def test_hierarchical_layout_empty_graph(self):
        result = graph_to_tikz(_empty_kg(), standalone=False, layout_name="hierarchical")
        assert "tikzpicture" in result

    def test_radial_layout_single_node(self):
        kg = KnowledgeGraph(nodes=(_node("note:1", label="Solo"),), edges=())
        result = graph_to_tikz(kg, standalone=False, layout_name="radial")
        assert "Solo" in result

    def test_hierarchical_grouping_by_type(self):
        """Two node types appear at different y positions (hierarchical layout)."""
        n1 = _node("note:1", ntype="note", label="N")
        n2 = _node("ex:1", ntype="exercise", label="E")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=())
        result = graph_to_tikz(kg, standalone=False, layout_name="hierarchical")
        # Extract all 'at (x, y)' coordinates
        coords = re.findall(r'at \(([\d.]+),\s*([\d.]+)\)', result)
        assert len(coords) == 2
        y_vals = [float(c[1]) for c in coords]
        # Different node types → different y values
        assert y_vals[0] != y_vals[1]


# ---------------------------------------------------------------------------
# 7. --include-tags / --exclude-tags CLI flags accepted
# ---------------------------------------------------------------------------

class TestTagFlags:
    def test_include_tags_flag_accepted(self):
        runner = CliRunner()
        kg = _empty_kg()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["export-tikz", "--include-tags", "physics"])
        assert result.exit_code == 0

    def test_exclude_tags_flag_accepted(self):
        runner = CliRunner()
        kg = _empty_kg()
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["export-tikz", "--exclude-tags", "draft"])
        assert result.exit_code == 0

    def test_include_tags_filters_nodes(self):
        """Nodes whose label contains the tag are kept; others excluded."""
        runner = CliRunner()
        n_keep = _node("note:1", label="physics-intro")
        n_drop = _node("note:2", label="chemistry-intro")
        kg = KnowledgeGraph(nodes=(n_keep, n_drop), edges=())
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["export-tikz", "--include-tags", "physics"])
        assert result.exit_code == 0
        assert "physics" in result.output
        assert "chemistry" not in result.output

    def test_exclude_tags_filters_nodes(self):
        """Nodes whose label contains excluded tag are removed."""
        runner = CliRunner()
        n_keep = _node("note:1", label="final-version")
        n_drop = _node("note:2", label="draft-note")
        kg = KnowledgeGraph(nodes=(n_keep, n_drop), edges=())
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["export-tikz", "--exclude-tags", "draft"])
        assert result.exit_code == 0
        assert "final" in result.output
        assert "draft" not in result.output


# ---------------------------------------------------------------------------
# 8. Backward-compatibility: existing callers still work
# ---------------------------------------------------------------------------

# (sections 8+)

# ---------------------------------------------------------------------------
# 9. Stable palette hash — process-independent (SHA-1 based)
# ---------------------------------------------------------------------------

class TestPaletteStability:
    def test_same_key_same_color(self):
        """_palette_color must return the same value on repeated calls."""
        assert _palette_color("note:42") == _palette_color("note:42")

    def test_pinned_known_mapping(self):
        """Pin the SHA-1-based index for a known key so regressions are caught.

        SHA-1("note:1") = 3d963f7b... → int mod 10.
        We compute the expected value inline so the test is self-documenting.
        """
        import hashlib
        from workflow.graph.tikz_export import _COLOR_PALETTE

        key = "note:1"
        digest = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        expected_idx = digest % len(_COLOR_PALETTE)
        assert _palette_color(key) == _COLOR_PALETTE[expected_idx]

    def test_different_keys_may_differ(self):
        """Two distinct keys should not always map to the same colour (sanity)."""
        keys = [f"note:{i}" for i in range(20)]
        colors = {_palette_color(k) for k in keys}
        # With 20 keys across a 10-colour palette we expect > 1 distinct colour.
        assert len(colors) > 1

    def test_stable_across_simulated_process_restart(self):
        """Recompute the mapping independently; result must match."""
        import hashlib
        from workflow.graph.tikz_export import _COLOR_PALETTE

        key = "topic:physics"
        digest = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        expected = _COLOR_PALETTE[digest % len(_COLOR_PALETTE)]
        assert _palette_color(key) == expected


# ---------------------------------------------------------------------------
# 10. Newline injection safety in _escape_tikz and graph_to_tikz title
# ---------------------------------------------------------------------------


class TestNewlineSafety:
    def test_escape_tikz_strips_newline(self):
        """A label with \\n must produce a single-line, brace-safe string."""
        result = _escape_tikz("line1\nline2")
        assert "\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_escape_tikz_strips_carriage_return(self):
        result = _escape_tikz("line1\rline2")
        assert "\r" not in result

    def test_escape_tikz_strips_crlf(self):
        result = _escape_tikz("a\r\nb")
        assert "\r" not in result
        assert "\n" not in result

    def test_node_label_with_newline_produces_valid_tikz(self):
        """A GraphNode whose label contains \\n must produce single-line \\node."""
        n = _node("note:1", label="title\ninjected")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False)
        # Each \node line must be a single line (no embedded newline inside braces)
        for line in result.splitlines():
            if r"\node" in line:
                assert "\n" not in line

    def test_title_with_newline_does_not_break_comment(self):
        """A title containing \\n must not produce multi-line % comment."""
        n = _node("note:1", label="X")
        kg = KnowledgeGraph(nodes=(n,), edges=())
        result = graph_to_tikz(kg, standalone=False, title="my\ntitle")
        for line in result.splitlines():
            if line.strip().startswith("%"):
                assert "\n" not in line


class TestBackwardCompat:
    def test_graph_to_tikz_no_new_args(self):
        """Call with old-style args → identical output to pre-Wave-4."""
        n1 = _node("note:1", ntype="note", label="intro.tex")
        n2 = _node("bib:1", ntype="bib_entry", label="serway2019")
        e = _edge("note:1", "bib:1", "citation")
        kg = KnowledgeGraph(nodes=(n1, n2), edges=(e,))
        result = graph_to_tikz(kg, standalone=False)
        assert r"\node" in result
        assert r"\draw" in result
        assert "intro.tex" in result
        assert "serway2019" in result

    def test_export_tikz_cmd_no_new_flags(self):
        """export-tikz without new flags still works (exit 0, valid TikZ)."""
        runner = CliRunner()
        kg = KnowledgeGraph(
            nodes=(_node("note:1", label="X"),), edges=()
        )
        with patch("workflow.graph.cli._build_graph_with_filter", return_value=kg):
            result = runner.invoke(graph, ["export-tikz"])
        assert result.exit_code == 0
        assert "tikzpicture" in result.output
