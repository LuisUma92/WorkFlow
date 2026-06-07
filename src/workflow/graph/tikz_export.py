"""TikZ graph export for the WorkFlow knowledge graph.

Renders a KnowledgeGraph as LaTeX/TikZ code using a simple
Fruchterman-Reingold force-directed layout.
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from workflow.graph.domain import KnowledgeGraph, GraphNode  # noqa: F401

__all__ = [
    "LayoutNode",
    "spring_layout",
    "radial_layout",
    "hierarchical_layout",
    "graph_to_tikz",
    "_select_layout",
    "_make_color_fn",
]

_DEFAULT_TIKZ_COLORS: dict[str, str] = {
    "note": "blue!60",
    "exercise": "red!60",
    "bib_entry": "green!60",
    "content": "orange!60",
    "topic": "violet!60",
    "course": "teal!60",
}

# Stable palette for color_by="main_topic" / color_by="tag".
# Uses a deterministic hash of the attribute key → palette index.
_COLOR_PALETTE: tuple[str, ...] = (
    "red!70",
    "blue!70",
    "green!70",
    "orange!70",
    "violet!70",
    "teal!70",
    "yellow!60",
    "cyan!70",
    "magenta!60",
    "lime!60",
)


def _palette_color(key: str) -> str:
    """Map *key* to a stable TikZ colour from the palette.

    Uses a SHA-1 digest so the mapping is deterministic across processes
    (unlike Python's PYTHONHASHSEED-salted ``hash()``).
    """
    digest = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    idx = digest % len(_COLOR_PALETTE)
    return _COLOR_PALETTE[idx]


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


# ---------------------------------------------------------------------------
# Radial layout — BFS rings from the most-connected node
# ---------------------------------------------------------------------------

def _assign_ring_depths(
    nodes: list[GraphNode],
    graph: KnowledgeGraph,
    center_id: str,
) -> dict[str, int]:
    """BFS from *center_id*; assign ring depth to every node.

    Disconnected nodes are placed in an extra outer ring beyond the BFS horizon.
    """
    adj = graph.adjacency()
    node_ids = graph.node_ids()
    visited: dict[str, int] = {center_id: 0}
    queue: deque[str] = deque([center_id])
    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, []):
            if neighbor not in visited and neighbor in node_ids:
                visited[neighbor] = visited[current] + 1
                queue.append(neighbor)
    max_depth = max(visited.values()) if visited else 0
    for nd in nodes:
        if nd.node_id not in visited:
            max_depth += 1
            visited[nd.node_id] = max_depth
    return visited


def _place_rings(
    nodes: list[GraphNode],
    depths: dict[str, int],
    cx: float,
    cy: float,
    outer_radius: float,
) -> list[LayoutNode]:
    """Convert BFS depth assignments into 2-D positions."""
    rings: dict[int, list[GraphNode]] = defaultdict(list)
    for nd in nodes:
        rings[depths[nd.node_id]].append(nd)
    total_rings = max(rings.keys())
    result: list[LayoutNode] = []
    for depth in sorted(rings.keys()):
        ring_nodes = rings[depth]
        if depth == 0:
            result.append(LayoutNode(ring_nodes[0], cx, cy))
            continue
        radius = outer_radius * depth / (total_rings + 1)
        for j, nd in enumerate(ring_nodes):
            angle = 2.0 * math.pi * j / len(ring_nodes)
            result.append(LayoutNode(nd, cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return result


def radial_layout(
    graph: KnowledgeGraph,
    *,
    width: float = 16.0,
    height: float = 12.0,
) -> tuple[LayoutNode, ...]:
    """Arrange nodes in concentric rings using BFS from the highest-degree node.

    Parameters
    ----------
    graph:
        The graph to lay out.
    width, height:
        Bounding box in centimetres.

    Returns
    -------
    tuple[LayoutNode, ...]
        Immutable sequence of positioned nodes.
    """
    nodes = list(graph.nodes)
    if not nodes:
        return ()

    cx, cy = width / 2.0, height / 2.0

    if len(nodes) == 1:
        return (LayoutNode(nodes[0], cx, cy),)

    # Find center as most-connected node (highest undirected degree).
    degree: Counter[str] = Counter()
    for e in graph.edges:
        degree[e.source_id] += 1
        degree[e.target_id] += 1
    center_id = max((nd.node_id for nd in nodes), key=lambda nid: degree[nid])

    depths = _assign_ring_depths(nodes, graph, center_id)
    outer_radius = min(width, height) / 2.0 * 0.85
    return tuple(_place_rings(nodes, depths, cx, cy, outer_radius))


# ---------------------------------------------------------------------------
# Hierarchical layout — horizontal layers by node_type
# ---------------------------------------------------------------------------

def hierarchical_layout(
    graph: KnowledgeGraph,
    *,
    width: float = 16.0,
    height: float = 12.0,
) -> tuple[LayoutNode, ...]:
    """Arrange nodes in horizontal layers grouped by *node_type*.

    Parameters
    ----------
    graph:
        The graph to lay out.
    width, height:
        Bounding box in centimetres.

    Returns
    -------
    tuple[LayoutNode, ...]
        Immutable sequence of positioned nodes.
    """
    nodes = list(graph.nodes)
    if not nodes:
        return ()

    # Group by node_type (stable ordering via sorted).
    layers: dict[str, list[GraphNode]] = defaultdict(list)
    for nd in nodes:
        layers[nd.node_type].append(nd)

    layer_types = sorted(layers.keys())
    n_layers = len(layer_types)
    result: list[LayoutNode] = []
    for i, ntype in enumerate(layer_types):
        layer_nodes = layers[ntype]
        y = height * (i + 1) / (n_layers + 1)
        for j, nd in enumerate(layer_nodes):
            x = width * (j + 1) / (len(layer_nodes) + 1)
            result.append(LayoutNode(nd, x, y))

    return tuple(result)


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
    """Escape LaTeX special characters for TikZ labels.

    Newlines (``\\n`` / ``\\r``) are replaced with a space first so that
    user-controlled node labels cannot break out of TikZ ``\\node{...}``
    braces or corrupt ``%``-comment lines.
    """
    text = text.replace('\r', ' ').replace('\n', ' ')
    for char in ('\\', '{', '}', '$', '&', '#', '_', '%', '~', '^'):
        text = text.replace(char, '\\' + char)
    return text


def _tikz_color(node_type: str, node_colors: dict[str, str]) -> str:
    return node_colors.get(node_type, _DEFAULT_TIKZ_COLORS.get(node_type, "gray!40"))


def _select_layout(
    graph: KnowledgeGraph,
    layout: tuple[LayoutNode, ...] | None,
    layout_name: str,
) -> tuple[LayoutNode, ...]:
    """Return *layout* if provided, else compute one using *layout_name*."""
    if layout is not None:
        return layout
    if layout_name == "radial":
        return radial_layout(graph)
    if layout_name == "hierarchical":
        return hierarchical_layout(graph)
    return spring_layout(graph)


def _make_color_fn(
    color_by: str | None,
    node_colors: dict[str, str] | None,
) -> Callable[[GraphNode], str]:
    """Return a callable ``(GraphNode) -> str`` for the chosen colour strategy.

    ``color_by="main_topic"`` and ``color_by="tag"`` both hash the node's
    ``node_id`` to a palette colour — they do **not** query real MainTopic or
    Tag DB data (``GraphNode`` does not carry that metadata).  The mapping is
    stable across processes thanks to SHA-1 (see ``_palette_color``).
    """
    if color_by is None or color_by == "type":
        colors: dict[str, str] = {**_DEFAULT_TIKZ_COLORS, **(node_colors or {})}
        return lambda node: _tikz_color(node.node_type, colors)
    # "main_topic", "tag", or future keys — stable hash of node_id to palette.
    return lambda node: _palette_color(node.node_id)


def graph_to_tikz(
    graph: KnowledgeGraph,
    *,
    layout: tuple[LayoutNode, ...] | None = None,
    standalone: bool = True,
    title: str = "",
    node_colors: dict[str, str] | None = None,
    layout_name: str = "force",
    color_by: str | None = None,
) -> str:
    """Render *graph* as TikZ/LaTeX source.

    Parameters
    ----------
    graph:
        The knowledge graph to render.
    layout:
        Pre-computed layout (``tuple[LayoutNode, ...]``); if ``None``, the
        algorithm selected by *layout_name* is called automatically.
    standalone:
        Wrap in ``\\documentclass[tikz]{standalone}`` when ``True``.
    title:
        Optional title drawn as a comment above the diagram.
    node_colors:
        Per-type TikZ colour overrides (e.g. ``{"note": "blue!80"}``).
        Ignored when *color_by* is not ``None`` or ``"type"``.
    layout_name:
        Layout algorithm to use when *layout* is ``None``.
        One of ``"force"`` (default, Fruchterman-Reingold), ``"radial"``
        (BFS rings from highest-degree node), or ``"hierarchical"``
        (horizontal layers by node_type).
    color_by:
        Colouring strategy for nodes.  ``None`` / ``"type"`` → default
        type-based palette (unchanged behaviour).  ``"main_topic"`` or
        ``"tag"`` → each node gets a stable palette colour derived from its
        ``node_id`` via a SHA-1 hash (process-stable).  Note: these modes do
        **not** use real MainTopic or Tag DB data; ``GraphNode`` does not carry
        that metadata.  The coloring is purely id-hash-based.

    Returns
    -------
    str
        LaTeX source string.
    """
    layout = _select_layout(graph, layout, layout_name)
    get_color = _make_color_fn(color_by, node_colors)
    id_to_name: dict[str, str] = {ln.node.node_id: _safe_node_name(ln.node.node_id) for ln in layout}

    body_lines: list[str] = []

    if title:
        # Sanitize newlines so the title cannot break the % comment line.
        safe_title = title.replace('\r', ' ').replace('\n', ' ')
        body_lines.append(f"  % {safe_title}")

    # Nodes
    for ln in layout:
        color = get_color(ln.node)
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
