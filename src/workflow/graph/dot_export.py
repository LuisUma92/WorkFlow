"""Graphviz DOT export for the WorkFlow knowledge graph.

Renders a KnowledgeGraph as a Graphviz DOT digraph string.
"""
from __future__ import annotations

from workflow.graph.domain import KnowledgeGraph, GraphNode, GraphEdge  # noqa: F401

__all__ = ["graph_to_dot", "_DEFAULT_COLORS"]

_DEFAULT_COLORS: dict[str, str] = {
    "note": "#4A90D9",
    "exercise": "#E74C3C",
    "bib_entry": "#2ECC71",
    "content": "#F39C12",
    "topic": "#9B59B6",
    "course": "#1ABC9C",
}

_ORPHAN_BORDER = "color=red, penwidth=3"


def _escape_dot(value: str) -> str:
    """Escape special characters for a DOT double-quoted string."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    return value


def _node_id(node_id: str) -> str:
    """Return a quoted DOT identifier for a node id."""
    return f'"{_escape_dot(node_id)}"'


def _node_line(
    node: GraphNode,
    colors: dict[str, str],
    highlight_orphan: bool,
) -> str:
    """Render a single node declaration."""
    fill = colors.get(node.node_type, "#CCCCCC")
    label = _escape_dot(node.label)
    attrs = f'label="{label}", fillcolor="{fill}", fontcolor=white'
    if highlight_orphan:
        attrs += f", {_ORPHAN_BORDER}"
    return f'  {_node_id(node.node_id)} [{attrs}];'


def _edge_line(edge: GraphEdge) -> str:
    """Render a single edge declaration."""
    label = _escape_dot(edge.edge_type)
    return f'  {_node_id(edge.source_id)} -> {_node_id(edge.target_id)} [label="{label}"];'


def graph_to_dot(
    graph: KnowledgeGraph,
    *,
    title: str = "WorkFlow Knowledge Graph",
    rankdir: str = "LR",
    node_colors: dict[str, str] | None = None,
    highlight_orphans: bool = False,
) -> str:
    """Render *graph* as a Graphviz DOT digraph string.

    Parameters
    ----------
    graph:
        The knowledge graph to render.
    title:
        Digraph title used as the DOT graph name.
    rankdir:
        Graphviz rankdir attribute (``"LR"`` or ``"TB"``).
    node_colors:
        Per-type fill colour overrides.  Missing types fall back to
        :data:`_DEFAULT_COLORS` and finally ``"#CCCCCC"``.
    highlight_orphans:
        When ``True``, nodes with degree 0 get a red border.

    Returns
    -------
    str
        A complete DOT digraph string.
    """
    colors: dict[str, str] = {**_DEFAULT_COLORS, **(node_colors or {})}

    # Compute degree for orphan detection
    connected: set[str] = set()
    if highlight_orphans:
        for edge in graph.edges:
            connected.add(edge.source_id)
            connected.add(edge.target_id)

    escaped_title = _escape_dot(title)
    lines: list[str] = [
        f'digraph "{escaped_title}" {{',
        f"  rankdir={rankdir};",
        "  node [shape=box, style=filled];",
        "",
    ]

    for node in graph.nodes:
        is_orphan = highlight_orphans and node.node_id not in connected
        lines.append(_node_line(node, colors, is_orphan))

    if graph.nodes and graph.edges:
        lines.append("")

    for edge in graph.edges:
        lines.append(_edge_line(edge))

    lines.append("}")
    return "\n".join(lines)
