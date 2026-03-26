"""TikZ graph export for the WorkFlow knowledge graph.

Renders a KnowledgeGraph as LaTeX/TikZ code using a simple
Fruchterman-Reingold force-directed layout.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from workflow.graph.domain import KnowledgeGraph, GraphNode  # noqa: F401

__all__ = ["LayoutNode", "spring_layout", "graph_to_tikz"]

_DEFAULT_TIKZ_COLORS: dict[str, str] = {
    "note": "blue!60",
    "exercise": "red!60",
    "bib_entry": "green!60",
    "content": "orange!60",
    "topic": "violet!60",
    "course": "teal!60",
}


@dataclass(frozen=True)
class LayoutNode:
    """A graph node together with its 2-D position."""

    node: GraphNode
    x: float
    y: float


# ---------------------------------------------------------------------------
# Force-directed layout (Fruchterman-Reingold)
# ---------------------------------------------------------------------------

def spring_layout(
    graph: KnowledgeGraph,
    *,
    iterations: int = 50,
    width: float = 16.0,
    height: float = 12.0,
    seed: int = 42,
) -> tuple[LayoutNode, ...]:
    """Compute a simple Fruchterman-Reingold layout.

    Parameters
    ----------
    graph:
        The graph to lay out.
    iterations:
        Number of simulation steps.
    width, height:
        Bounding box in centimetres.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    tuple[LayoutNode, ...]
        Immutable sequence of positioned nodes in the same order as
        *graph.nodes*.
    """
    _MAX_LAYOUT_NODES = 500

    if len(graph.nodes) > _MAX_LAYOUT_NODES:
        import warnings
        warnings.warn(
            f"Graph has {len(graph.nodes)} nodes; spring layout may be slow. "
            "Consider using DOT export for large graphs."
        )

    nodes = list(graph.nodes)
    n = len(nodes)
    if n == 0:
        return ()

    rng = random.Random(seed)

    # Initial positions — random within the bounding box
    xs = [rng.uniform(0.1 * width, 0.9 * width) for _ in range(n)]
    ys = [rng.uniform(0.1 * height, 0.9 * height) for _ in range(n)]

    if n == 1:
        return (LayoutNode(nodes[0], xs[0], ys[0]),)

    # Build adjacency as a set of index pairs for O(1) lookup
    id_to_idx: dict[str, int] = {node.node_id: i for i, node in enumerate(nodes)}
    adj: set[tuple[int, int]] = set()
    for edge in graph.edges:
        si = id_to_idx.get(edge.source_id)
        ti = id_to_idx.get(edge.target_id)
        if si is not None and ti is not None:
            adj.add((si, ti))
            adj.add((ti, si))

    area = width * height
    k = math.sqrt(area / n)  # ideal spring length
    temperature = width / 10.0
    cooling = temperature / (iterations + 1)

    for _step in range(iterations):
        dx, dy = _repulsive_forces(n, xs, ys, k)
        _attractive_forces(adj, xs, ys, k, dx, dy)
        _apply_displacements(n, xs, ys, dx, dy, temperature, width, height)
        temperature -= cooling

    return tuple(LayoutNode(nodes[i], xs[i], ys[i]) for i in range(n))


def _repulsive_forces(
    n: int, xs: list[float], ys: list[float], k: float
) -> tuple[list[float], list[float]]:
    """Return repulsive displacement vectors for all nodes."""
    dx = [0.0] * n
    dy = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            delta_x = xs[i] - xs[j]
            delta_y = ys[i] - ys[j]
            dist = math.sqrt(delta_x ** 2 + delta_y ** 2) or 0.001
            force = k * k / dist
            fx = (delta_x / dist) * force
            fy = (delta_y / dist) * force
            dx[i] += fx
            dy[i] += fy
            dx[j] -= fx
            dy[j] -= fy
    return dx, dy


def _attractive_forces(
    adj: set[tuple[int, int]],
    xs: list[float],
    ys: list[float],
    k: float,
    dx: list[float],
    dy: list[float],
) -> None:
    """Apply attractive forces in-place on dx, dy."""
    for (si, ti) in adj:
        if si >= ti:
            continue
        delta_x = xs[si] - xs[ti]
        delta_y = ys[si] - ys[ti]
        dist = math.sqrt(delta_x ** 2 + delta_y ** 2) or 0.001
        force = dist * dist / k
        fx = (delta_x / dist) * force
        fy = (delta_y / dist) * force
        dx[si] -= fx
        dy[si] -= fy
        dx[ti] += fx
        dy[ti] += fy


def _apply_displacements(
    n: int,
    xs: list[float],
    ys: list[float],
    dx: list[float],
    dy: list[float],
    temperature: float,
    width: float,
    height: float,
) -> None:
    """Apply capped displacements and clamp positions to the bounding box."""
    for i in range(n):
        disp = math.sqrt(dx[i] ** 2 + dy[i] ** 2) or 0.001
        cap = min(disp, temperature)
        xs[i] += (dx[i] / disp) * cap
        ys[i] += (dy[i] / disp) * cap
        xs[i] = max(0.0, min(width, xs[i]))
        ys[i] = max(0.0, min(height, ys[i]))


# ---------------------------------------------------------------------------
# TikZ rendering
# ---------------------------------------------------------------------------

def _safe_node_name(node_id: str) -> str:
    """Convert a node id into a safe TikZ node name (alphanumeric + underscore)."""
    return "".join(c if c.isalnum() else "_" for c in node_id)


def _escape_tikz(text: str) -> str:
    """Escape LaTeX special characters for TikZ labels."""
    for char in ('\\', '{', '}', '$', '&', '#', '_', '%', '~', '^'):
        text = text.replace(char, '\\' + char)
    return text


def _tikz_color(node_type: str, node_colors: dict[str, str]) -> str:
    return node_colors.get(node_type, _DEFAULT_TIKZ_COLORS.get(node_type, "gray!40"))


def graph_to_tikz(
    graph: KnowledgeGraph,
    *,
    layout: tuple[LayoutNode, ...] | None = None,
    standalone: bool = True,
    title: str = "",
    node_colors: dict[str, str] | None = None,
) -> str:
    """Render *graph* as TikZ/LaTeX source.

    Parameters
    ----------
    graph:
        The knowledge graph to render.
    layout:
        Pre-computed layout; if ``None``, :func:`spring_layout` is called.
    standalone:
        Wrap in ``\\documentclass[tikz]{standalone}`` when ``True``.
    title:
        Optional title drawn as a node above the diagram.
    node_colors:
        Per-type TikZ colour overrides (e.g. ``{"note": "blue!80"}``).

    Returns
    -------
    str
        LaTeX source string.
    """
    if layout is None:
        layout = spring_layout(graph)

    colors: dict[str, str] = {**_DEFAULT_TIKZ_COLORS, **(node_colors or {})}
    id_to_name: dict[str, str] = {ln.node.node_id: _safe_node_name(ln.node.node_id) for ln in layout}

    body_lines: list[str] = []

    if title:
        body_lines.append(f"  % {title}")

    # Nodes
    for ln in layout:
        color = _tikz_color(ln.node.node_type, colors)
        name = id_to_name[ln.node.node_id]
        label = _escape_tikz(ln.node.label)
        x_str = f"{ln.x:.2f}"
        y_str = f"{ln.y:.2f}"
        body_lines.append(
            f"  \\node[fill={color}, draw, rounded corners] ({name}) "
            f"at ({x_str}, {y_str}) {{{label}}};"
        )

    if layout and graph.edges:
        body_lines.append("")

    # Edges
    id_set = {ln.node.node_id for ln in layout}
    for edge in graph.edges:
        if edge.source_id in id_set and edge.target_id in id_set:
            src = id_to_name[edge.source_id]
            tgt = id_to_name[edge.target_id]
            body_lines.append(f"  \\draw[->] ({src}) -- ({tgt});")

    tikz_lines = [
        "\\begin{tikzpicture}",
        *body_lines,
        "\\end{tikzpicture}",
    ]

    if standalone:
        return "\n".join([
            "\\documentclass[tikz]{standalone}",
            "\\begin{document}",
            *tikz_lines,
            "\\end{document}",
        ])

    return "\n".join(tikz_lines)
