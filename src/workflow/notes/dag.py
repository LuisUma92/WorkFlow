"""DAG cycle detection for structural NoteEdges (ITEP-0013 P2.4).

Only structural edges with a resolved target_id are included.
Associative edges and unresolved (target_id=None) edges are excluded.
"""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.notes import NoteEdge

__all__ = ["detect_structural_cycles"]


def _canonical_cycle(cycle: list[int]) -> tuple[int, ...]:
    """Normalize a closed cycle path [a, b, ..., a] to a canonical frozenset key.

    Rotates the cycle body (excluding the repeated last element) to start at
    the minimum node, enabling deduplication across DFS entry points.
    """
    body = cycle[:-1]  # drop the repeated tail
    min_idx = body.index(min(body))
    rotated = body[min_idx:] + body[:min_idx]
    return tuple(rotated)


def _find_cycles(adj: dict[int, list[int]]) -> list[list[int]]:
    """Iterative DFS-based cycle detection (no recursion limit risk).

    Returns deduplicated cycles; each cycle is a list of note ids with
    first == last (closed path), e.g. [1, 3, 5, 1].
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[int, int] = {n: WHITE for n in adj}
    seen_canonical: set[tuple[int, ...]] = set()
    cycles: list[list[int]] = []

    for start in list(adj.keys()):
        if color[start] != WHITE:
            continue

        path: list[int] = []
        # Stack items: (node, neighbor_iterator)
        stack: list[tuple[int, Iterator[int]]] = [
            (start, iter(adj.get(start, [])))
        ]
        color[start] = GRAY
        path.append(start)

        while stack:
            node, neighbors = stack[-1]
            try:
                v = next(neighbors)
                v_color = color.get(v, WHITE)
                if v_color == WHITE:
                    color[v] = GRAY
                    path.append(v)
                    stack.append((v, iter(adj.get(v, []))))
                elif v_color == GRAY:
                    # Back edge → cycle
                    idx = path.index(v)
                    cycle = path[idx:] + [v]
                    key = _canonical_cycle(cycle)
                    if key not in seen_canonical:
                        seen_canonical.add(key)
                        cycles.append(cycle)
                # BLACK: already fully processed — skip
            except StopIteration:
                color[node] = BLACK
                path.pop()
                stack.pop()

    return cycles


def detect_structural_cycles(session: Session) -> list[list[int]]:
    """Return all cycles in the resolved structural-edge subgraph.

    Each cycle is a list of Note.id values: [src, ..., src] (closed path).
    Returns [] when the graph is acyclic or empty.

    Note: loads all resolved structural edges into memory. Suitable for
    typical Zettelkasten vaults (thousands of notes).
    """
    rows = session.execute(
        select(NoteEdge.source_id, NoteEdge.target_id).where(
            NoteEdge.edge_class == "structural",
            NoteEdge.target_id.is_not(None),
        )
    ).all()

    adj: dict[int, list[int]] = {}
    for src, tgt in rows:
        adj.setdefault(src, [])
        if tgt not in adj[src]:
            adj[src].append(tgt)
        adj.setdefault(tgt, [])  # ensure isolated targets are coloured

    return _find_cycles(adj)
