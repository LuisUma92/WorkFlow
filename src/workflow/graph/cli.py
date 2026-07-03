"""Click command group for WorkFlow knowledge graph analysis and export.

Commands:
  graph orphans      — list nodes with no connections
  graph stats        — show graph summary statistics
  graph export-dot   — export as Graphviz DOT
  graph export-tikz  — export as TikZ/LaTeX
  graph clusters     — show topic clusters (requires networkx)
  graph neighbors    — show neighbours of a node
"""

from __future__ import annotations

import json as _json
import re as _re
from collections import deque as _deque
from pathlib import Path
from typing import Any

import click
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.errors import with_schema_guard
from workflow.graph.analysis import (
    compute_stats,
    directed_bfs,
    find_lineage_roots,
    find_orphans,
    neighbors,
    neighbors_detailed,
)
from workflow.graph.collectors import (
    TaxonomyFilter,
    build_knowledge_graph,
    filter_graph_by_taxonomy,
    resolve_taxonomy_filter,
)
from workflow.graph.domain import GraphNode, KnowledgeGraph
from workflow.graph.node_ids import is_note, parse_note_id
from workflow.vault.paths import resolve_vault_root


# ── Graph builder ───────────────────────────────────────────────────────────


def _build_graph(
    project: str,
    tf: TaxonomyFilter | None = None,
) -> KnowledgeGraph:
    """Build knowledge graph from the global DB (ITEP-0011 P3).

    ``project`` is retained for forward compatibility (P5 ProjectNote)
    but is currently unused — all graph sources live on GlobalBase.

    If *tf* is provided and non-empty, the graph is filtered to nodes
    reachable from the taxonomy specification.
    """
    del project  # reserved for ITEP-0011 P5 routing
    global_engine = init_global_db()
    with Session(global_engine) as gsession:
        kg = build_knowledge_graph(gsession)
        if tf is not None and not tf.is_empty():
            kg = filter_graph_by_taxonomy(kg, gsession, tf)
        return kg


def _resolve_filter(
    session: Session,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> TaxonomyFilter:
    """Resolve CLI slug strings to a TaxonomyFilter; raise ClickException on miss."""
    try:
        return resolve_taxonomy_filter(
            session,
            main_topic=main_topic,
            discipline_area=discipline_area,
            topic=topic,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _build_graph_with_filter(
    project: str,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
    engine: Engine | None = None,
) -> KnowledgeGraph:
    """Build + filter the knowledge graph in a single DB session."""
    del project  # reserved for ITEP-0011 P5 routing
    global_engine = engine or init_global_db()
    with Session(global_engine) as gsession:
        tf = _resolve_filter(gsession, main_topic, discipline_area, topic)
        kg = build_knowledge_graph(gsession)
        if not tf.is_empty():
            kg = filter_graph_by_taxonomy(kg, gsession, tf)
        return kg


# ── Graph filter helpers (Wave 4) ────────────────────────────────────────────


def _build_full_graph(
    project: str,
    engine: Engine | None = None,
) -> KnowledgeGraph:
    """Build the full knowledge graph without any taxonomy filter."""
    del project  # reserved for ITEP-0011 P5 routing
    global_engine = engine or init_global_db()
    with Session(global_engine) as gsession:
        return build_knowledge_graph(gsession)


def _expand_by_depth(
    full_kg: KnowledgeGraph,
    seed_kg: KnowledgeGraph,
    depth: int,
) -> KnowledgeGraph:
    """Expand *seed_kg* by up to *depth* hops in *full_kg*.

    Multi-source BFS from every node in *seed_kg*, traversing edges in
    *full_kg*.  Returns a subgraph containing all reachable nodes and the
    induced edges from *full_kg*.

    depth=0 returns *seed_kg* unchanged.
    """
    if depth <= 0:
        return seed_kg

    seed_ids = seed_kg.node_ids()
    all_node_ids = full_kg.node_ids()
    adj = full_kg.adjacency()

    # Multi-source BFS: start at every seed node simultaneously.
    visited: dict[str, int] = {nid: 0 for nid in seed_ids if nid in all_node_ids}
    queue: _deque[tuple[str, int]] = _deque((nid, 0) for nid in visited)

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited and neighbor in all_node_ids:
                visited[neighbor] = current_depth + 1
                queue.append((neighbor, current_depth + 1))

    expanded_ids = frozenset(visited.keys())
    node_map = {n.node_id: n for n in full_kg.nodes}
    exp_nodes = tuple(node_map[nid] for nid in expanded_ids if nid in node_map)
    exp_edges = tuple(
        e for e in full_kg.edges
        if e.source_id in expanded_ids and e.target_id in expanded_ids
    )
    return KnowledgeGraph(nodes=exp_nodes, edges=exp_edges)


def _parse_cluster_name(name: str, max_count: int) -> int:
    """Parse a cluster name to a 0-based index.

    Accepts plain integers (``"1"``) or ``graph clusters``-style names
    (``"Cluster 1"``).  Raises ``click.ClickException`` on invalid input.
    """
    m = _re.fullmatch(r'(?:cluster\s+)?(\d+)', name.strip(), _re.IGNORECASE)
    if not m:
        raise click.ClickException(
            f"Invalid cluster name {name!r}. Use a number (1-based) or 'Cluster N'."
        )
    idx = int(m.group(1)) - 1  # convert to 0-based
    if idx < 0 or idx >= max_count:
        raise click.ClickException(
            f"Cluster {name!r} not found (valid range: 1–{max_count})."
        )
    return idx


def _filter_by_cluster(kg: KnowledgeGraph, cluster_name: str) -> KnowledgeGraph:
    """Return the subgraph matching the named community.

    Requires networkx; raises ``click.ClickException`` if unavailable.
    """
    from workflow.graph.clustering import detect_communities

    communities = detect_communities(kg)
    if communities is None:
        raise click.ClickException(
            "networkx is not installed. Install it with: pip install networkx"
        )
    if not communities:
        raise click.ClickException("No clusters found (graph is empty).")

    idx = _parse_cluster_name(cluster_name, len(communities))
    community = communities[idx]
    comm_ids = frozenset(n.node_id for n in community)
    sub_edges = tuple(
        e for e in kg.edges
        if e.source_id in comm_ids and e.target_id in comm_ids
    )
    return KnowledgeGraph(nodes=community, edges=sub_edges)


def _filter_by_tags(
    kg: KnowledgeGraph,
    include_tags: str | None,
    exclude_tags: str | None,
) -> KnowledgeGraph:
    """Filter graph nodes by tag presence in their label (substring match).

    *include_tags* / *exclude_tags* are comma-separated strings.  A node is
    kept when its label contains at least one include-tag (if any specified)
    and none of the exclude-tags.

    Note: ``GraphNode`` does not carry DB-level tag data, so this uses the
    node label as a best-effort proxy.  Full tag support would require tag
    metadata to be propagated through the collectors layer.
    """
    inc = [t.strip().lower() for t in include_tags.split(",") if t.strip()] if include_tags else []
    exc = [t.strip().lower() for t in exclude_tags.split(",") if t.strip()] if exclude_tags else []

    def _keep(node: GraphNode) -> bool:
        label = node.label.lower()
        if inc and not any(t in label for t in inc):
            return False
        if exc and any(t in label for t in exc):
            return False
        return True

    sub_nodes = tuple(n for n in kg.nodes if _keep(n))
    sub_ids = frozenset(n.node_id for n in sub_nodes)
    sub_edges = tuple(
        e for e in kg.edges
        if e.source_id in sub_ids and e.target_id in sub_ids
    )
    return KnowledgeGraph(nodes=sub_nodes, edges=sub_edges)


# ── CLI group ───────────────────────────────────────────────────────────────


@click.group()
def graph() -> None:
    """Knowledge graph analysis and export."""


# ── Shared filter options decorator ─────────────────────────────────────────


def _filter_options(cmd):  # type: ignore[no-untyped-def]
    """Attach --main-topic, --discipline-area, --topic filter options."""
    cmd = click.option(
        "--main-topic",
        "main_topic",
        default=None,
        metavar="SLUG_OR_ID",
        help="Restrict graph to nodes reachable from this MainTopic.",
    )(cmd)
    cmd = click.option(
        "--discipline-area",
        "discipline_area",
        default=None,
        metavar="SLUG_OR_ID",
        help="Restrict graph to nodes under this DisciplineArea.",
    )(cmd)
    cmd = click.option(
        "--topic",
        "topic",
        default=None,
        metavar="SLUG_OR_ID",
        help="Restrict graph to nodes under this Topic.",
    )(cmd)
    return cmd


# ── orphans ─────────────────────────────────────────────────────────────────


@graph.command()
@click.option(
    "--type",
    "node_type",
    type=click.Choice(
        ["note", "exercise", "bib_entry", "content", "topic", "course"],
        case_sensitive=False,
    ),
    default=None,
    help="Filter orphans by node type.",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--project", type=click.Path(exists=True), default=".")
@_filter_options
@with_schema_guard
def orphans(
    node_type: str | None,
    as_json: bool,
    project: str,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """List nodes with no connections, and lineage roots (no incoming structural edges)."""
    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)
    orphan_nodes = find_orphans(kg, node_type=node_type)
    lineage_root_nodes = find_lineage_roots(kg, node_type=node_type)

    # Build combined list: true orphans (is_lineage_root=False) +
    # lineage roots (is_lineage_root=True). Deduplicate by node_id.
    orphan_ids = {n.node_id for n in orphan_nodes}
    all_items = [
        (n, False) for n in orphan_nodes
    ] + [
        (n, True) for n in lineage_root_nodes if n.node_id not in orphan_ids
    ]

    if as_json:
        click.echo(
            _json.dumps(
                [
                    {
                        "node_id": n.node_id,
                        "node_type": n.node_type,
                        "label": n.label,
                        "is_lineage_root": is_root,
                    }
                    for n, is_root in all_items
                ]
            )
        )
        return

    if not all_items:
        click.echo("No orphaned nodes found.")
        return

    true_orphans = [(n, r) for n, r in all_items if not r]
    roots = [(n, r) for n, r in all_items if r]

    if true_orphans:
        for node, _ in true_orphans:
            click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}")
        click.echo(f"\nTotal: {len(true_orphans)} orphan(s).")

    if roots:
        click.echo("\nLineage roots (no incoming structural edges):")
        for node, _ in roots:
            click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}")
        click.echo(f"Total: {len(roots)} lineage root(s).")


# ── stats ────────────────────────────────────────────────────────────────────


@graph.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--project", type=click.Path(exists=True), default=".")
@_filter_options
@with_schema_guard
def stats(
    as_json: bool,
    project: str,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Show graph summary statistics."""
    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)
    s = compute_stats(kg)

    if as_json:
        click.echo(
            _json.dumps(
                {
                    "total_nodes": s.total_nodes,
                    "total_edges": s.total_edges,
                    "orphan_count": s.orphan_count,
                    "component_count": s.component_count,
                    "nodes_by_type": dict(s.nodes_by_type),
                    "edges_by_type": dict(s.edges_by_type),
                }
            )
        )
        return

    click.echo(f"Nodes: {s.total_nodes}")
    click.echo(f"Edges: {s.total_edges}")
    click.echo(f"Orphans: {s.orphan_count}")
    click.echo(f"Components: {s.component_count}")
    click.echo("\nNodes by type:")
    for ntype, count in s.nodes_by_type:
        click.echo(f"  {ntype}: {count}")
    click.echo("\nEdges by type:")
    for etype, count in s.edges_by_type:
        click.echo(f"  {etype}: {count}")


# ── export-dot ───────────────────────────────────────────────────────────────


@graph.command(name="export-dot")
@click.option("--project", type=click.Path(exists=True), default=".")
@click.option("--output", "-o", type=click.Path(), default=None)
@click.option("--highlight-orphans", is_flag=True)
@_filter_options
@with_schema_guard
def export_dot_cmd(
    project: str,
    output: str | None,
    highlight_orphans: bool,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Export graph as Graphviz DOT."""
    from workflow.graph.dot_export import graph_to_dot

    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)
    dot = graph_to_dot(kg, highlight_orphans=highlight_orphans)

    if output:
        Path(output).write_text(dot, encoding="utf-8")
        click.echo(f"DOT exported to {output}")
    else:
        click.echo(dot)


# ── export-tikz ──────────────────────────────────────────────────────────────


@graph.command(name="export-tikz")
@click.option("--project", type=click.Path(exists=True), default=".")
@click.option("--output", "-o", type=click.Path(), default=None)
@click.option("--standalone/--no-standalone", default=True)
@click.option(
    "--depth",
    default=0,
    show_default=True,
    help="Expand the filtered node set by N neighbour rings (0 = exact filter match).",
)
@click.option(
    "--cluster",
    "cluster",
    default=None,
    metavar="NAME",
    help=(
        "Restrict to a precomputed community from 'graph clusters'. "
        "Use a 1-based number or 'Cluster N'. "
        "Mutually exclusive with --main-topic."
    ),
)
@click.option(
    "--include-tags",
    "include_tags",
    default=None,
    metavar="TAG[,TAG...]",
    help=(
        "Keep only nodes whose display label contains at least one of these "
        "comma-separated strings (substring match on label text; not a DB tag query)."
    ),
)
@click.option(
    "--exclude-tags",
    "exclude_tags",
    default=None,
    metavar="TAG[,TAG...]",
    help=(
        "Remove nodes whose display label contains any of these comma-separated "
        "strings (substring match on label text; not a DB tag query)."
    ),
)
@click.option(
    "--layout",
    "layout_name",
    type=click.Choice(["force", "radial", "hierarchical"], case_sensitive=False),
    default="force",
    show_default=True,
    help="Node placement algorithm.",
)
@click.option(
    "--color-by",
    "color_by",
    type=click.Choice(["type", "main_topic", "tag"], case_sensitive=False),
    default=None,
    help=(
        "Colour nodes by this attribute.  'type' (default) uses per-type colours. "
        "'main_topic' and 'tag' both map each node's id to a stable palette colour "
        "via SHA-1 hash — they do NOT query real MainTopic/Tag DB data."
    ),
)
@_filter_options
@with_schema_guard
def export_tikz_cmd(
    project: str,
    output: str | None,
    standalone: bool,
    depth: int,
    cluster: str | None,
    include_tags: str | None,
    exclude_tags: str | None,
    layout_name: str,
    color_by: str | None,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Export graph as TikZ for LaTeX rendering.

    Filter flags (--main-topic, --discipline-area, --topic) narrow the graph
    to a taxonomy subgraph before rendering.  Use --depth to expand the
    matched node set by N BFS rings.  --cluster restricts to a precomputed
    community (mutually exclusive with --main-topic).
    """
    from workflow.graph.tikz_export import graph_to_tikz

    # Mutex guard: --main-topic + --cluster are incompatible.
    if main_topic and cluster:
        raise click.UsageError("--main-topic and --cluster are mutually exclusive.")

    full_kg: KnowledgeGraph | None = None

    if cluster:
        # Build graph (respecting any non-main_topic taxonomy filter) then
        # pick the named community.
        kg = _build_graph_with_filter(project, None, discipline_area, topic)
        kg = _filter_by_cluster(kg, cluster)
    else:
        kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)

    # Depth expansion: BFS from the filtered seed nodes into the full graph.
    if depth > 0 and (main_topic or discipline_area or topic or cluster):
        full_kg = _build_full_graph(project)
        kg = _expand_by_depth(full_kg, kg, depth)

    # Tag filters (label-based substring matching).
    if include_tags or exclude_tags:
        kg = _filter_by_tags(kg, include_tags, exclude_tags)

    tikz = graph_to_tikz(
        kg,
        standalone=standalone,
        layout_name=layout_name,
        color_by=color_by,
    )

    if output:
        Path(output).write_text(tikz, encoding="utf-8")
        click.echo(f"TikZ exported to {output}")
    else:
        click.echo(tikz)


# ── clusters ─────────────────────────────────────────────────────────────────


@graph.command()
@click.option("--project", type=click.Path(exists=True), default=".")
@_filter_options
@with_schema_guard
def clusters(
    project: str,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Show topic clusters (requires networkx)."""
    from workflow.graph.clustering import detect_communities

    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)
    communities = detect_communities(kg)

    if communities is None:
        click.echo("networkx is not installed. Install it with: pip install networkx")
        return

    if not communities:
        click.echo("No clusters found (graph is empty).")
        return

    for i, community in enumerate(communities, 1):
        click.echo(f"\nCluster {i} ({len(community)} nodes):")
        for node in community:
            click.echo(f"  [{node.node_type}] {node.label}")


# ── neighbors helpers ────────────────────────────────────────────────────────


def _fetch_note_rows(
    note_node_ids: list[str],
    engine: Engine,
) -> dict[str, dict[str, str]]:
    """Batch-query Note rows for a list of note-type node ids.

    Returns a dict  node_id → {"title": ..., "note_type": ..., "filename": ...}.
    Only ``note:<int>`` ids are considered; any other id is ignored, so the
    helper is safe regardless of caller filtering.
    """
    from workflow.db.models.notes import Note

    int_ids: list[int] = []
    for nid in note_node_ids:
        note_int_id = parse_note_id(nid)
        if note_int_id is None:
            continue
        int_ids.append(note_int_id)

    if not int_ids:
        return {}

    with Session(engine) as session:
        rows = session.scalars(select(Note).where(Note.id.in_(int_ids))).all()
        return {
            f"note:{r.id}": {
                "title": r.title or r.filename,
                "note_type": r.note_type or "permanent",
                "filename": r.filename,
            }
            for r in rows
        }


def _note_path(vault: Path, note_info: dict[str, str]) -> str:
    """Build absolute path string for a note row dict (note_type pre-coalesced)."""
    return str(vault / "notes" / note_info["note_type"] / note_info["filename"])


# ── neighbors ────────────────────────────────────────────────────────────────


@graph.command(name="neighbors")
@click.argument("node_id")
@click.option("--depth", default=1, help="Hop distance.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--project", type=click.Path(exists=True), default=".")
@_filter_options
@with_schema_guard
def neighbors_cmd(
    node_id: str,
    depth: int,
    as_json: bool,
    project: str,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Show neighbours of a node."""
    global_engine = init_global_db()
    kg = _build_graph_with_filter(
        project, main_topic, discipline_area, topic, engine=global_engine
    )

    if node_id not in kg.node_ids():
        raise click.ClickException(f"Node not found: {node_id}")

    if as_json:
        infos = neighbors_detailed(kg, node_id, depth=depth)
        vault = resolve_vault_root()

        # Collect all note-type ids (source + note neighbors) for ONE batch query.
        note_ids: list[str] = []
        if is_note(node_id):
            note_ids.append(node_id)
        for ni in infos:
            if is_note(ni.node.node_id):
                note_ids.append(ni.node.node_id)
        note_rows = _fetch_note_rows(note_ids, global_engine)

        # Build source object.
        src_node_map = {n.node_id: n for n in kg.nodes}
        src_node = src_node_map[node_id]
        if is_note(node_id) and node_id in note_rows:
            src_info = note_rows[node_id]
            src_title = src_info["title"]
            src_path: str | None = _note_path(vault, src_info)
        else:
            src_title = src_node.label
            src_path = None

        source_obj = {"id": node_id, "title": src_title, "path": src_path}

        # Build neighbor list.
        neighbor_list = []
        for ni in infos:
            nid = ni.node.node_id
            if is_note(nid) and nid in note_rows:
                nr = note_rows[nid]
                n_title: str | None = nr["title"]
                n_path: str | None = _note_path(vault, nr)
            else:
                n_title = ni.node.label
                n_path = None
            neighbor_list.append({
                "id": nid,
                "title": n_title,
                "path": n_path,
                "edge_class": None,
                "edge_type": ni.edge_type,
                "depth": ni.depth,
            })

        click.echo(_json.dumps({"source": source_obj, "neighbors": neighbor_list}))
        return

    subgraph = neighbors(kg, node_id, depth=depth)

    for node in subgraph.nodes:
        marker = " *" if node.node_id == node_id else ""
        click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}{marker}")
    click.echo(f"\n{len(subgraph.nodes)} node(s), {len(subgraph.edges)} edge(s).")


# ── trace / resume shared helpers ─────────────────────────────────────────────


def _structural_traversal(
    engine: Engine,
    zettel_id: str,
    *,
    reverse: bool,
    max_depth: int,
    node_budget: int,
) -> tuple[str, dict[str, int], dict[int, "Any"]]:
    """BFS traversal along structural NoteEdge rows.

    Args:
        reverse: When False, follow child→parent (trace ancestors).
                 When True, follow parent→child (resume descendants).

    Returns:
        ``(start_node_id, visited_depths, note_by_db_id)`` where
        ``visited_depths`` maps node_id → depth (includes start at depth 0) and
        ``note_by_db_id`` maps Note.id → Note row for all visited non-start nodes.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from workflow.db.models.notes import Note, NoteEdge

    with Session(engine) as session:
        note = session.scalars(
            select(Note).where(Note.zettel_id == zettel_id)
        ).first()
        if note is None:
            raise click.ClickException(f"Note {zettel_id!r} not found in DB.")

        rows = session.scalars(
            select(NoteEdge).where(
                NoteEdge.edge_class == "structural",
                NoteEdge.target_id.is_not(None),
            )
        ).all()

        adj: dict[str, list[str]] = {}
        for row in rows:
            src = f"note:{row.source_id}"
            tgt = f"note:{row.target_id}"
            key, val = (tgt, src) if reverse else (src, tgt)
            adj.setdefault(key, []).append(val)

        start = f"note:{note.id}"
        visited = directed_bfs(start, adj, max_depth=max_depth, node_budget=node_budget)

        other_ids = [
            int(nid[5:]) for nid in visited
            if nid != start and nid.startswith("note:")
            and nid[5:].lstrip("-").isdigit()
        ]
        rows_fetched = session.scalars(
            select(Note).where(Note.id.in_(other_ids))
        ).all() if other_ids else []
        note_by_id = {n.id: n for n in rows_fetched}

    return start, visited, note_by_id


def _emit_traversal(
    start: str,
    zettel_id: str,
    visited: dict[str, int],
    note_by_id: "dict[int, Any]",
    *,
    as_json: bool,
    empty_msg: str,
) -> None:
    """Render traversal result (JSON or text)."""
    entries = sorted(
        ((nid, d) for nid, d in visited.items() if nid != start),
        key=lambda x: x[1],
    )
    if as_json:
        result_nodes = []
        for nid, depth in entries:
            suffix = nid[len("note:"):]
            int_id = int(suffix) if suffix.lstrip("-").isdigit() else None
            n = note_by_id.get(int_id) if int_id is not None else None
            result_nodes.append({
                "node_id": nid,
                "zettel_id": n.zettel_id if n else None,
                "title": n.title if n else None,
                "depth": depth,
            })
        click.echo(_json.dumps({"start": zettel_id, "nodes": result_nodes}))
        return
    if not entries:
        click.echo(empty_msg)
        return
    for nid, depth in entries:
        suffix = nid[len("note:"):]
        int_id = int(suffix) if suffix.lstrip("-").isdigit() else None
        n = note_by_id.get(int_id) if int_id is not None else None
        label = (n.zettel_id or nid) if n else nid
        title = f" — {n.title}" if n and n.title else ""
        click.echo(f"  (depth {depth}) {label}{title}")


# ── trace ─────────────────────────────────────────────────────────────────────


@graph.command(name="trace")
@click.argument("zettel_id")
@click.option("--max-depth", "max_depth", type=int, default=10, show_default=True,
              help="Maximum BFS depth toward ancestors.")
@click.option("--node-budget", "node_budget", type=int, default=50, show_default=True,
              help="Stop traversal after collecting this many nodes.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@with_schema_guard
def trace_cmd(
    zettel_id: str,
    max_depth: int,
    node_budget: int,
    as_json: bool,
) -> None:
    """Trace lineage ancestors of a note along structural edges (BFS toward roots)."""
    global_engine = init_global_db()
    start, visited, note_by_id = _structural_traversal(
        global_engine, zettel_id,
        reverse=False, max_depth=max_depth, node_budget=node_budget,
    )
    _emit_traversal(
        start, zettel_id, visited, note_by_id,
        as_json=as_json,
        empty_msg=f"No ancestors found for {zettel_id!r}.",
    )


# ── resume ────────────────────────────────────────────────────────────────────


@graph.command(name="resume")
@click.argument("zettel_id")
@click.option("--max-depth", "max_depth", type=int, default=10, show_default=True,
              help="Maximum BFS depth toward descendants.")
@click.option("--node-budget", "node_budget", type=int, default=50, show_default=True,
              help="Stop traversal after collecting this many nodes.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@with_schema_guard
def resume_cmd(
    zettel_id: str,
    max_depth: int,
    node_budget: int,
    as_json: bool,
) -> None:
    """Show descendants of a note: notes that continue from it (BFS along structural edges)."""
    global_engine = init_global_db()
    start, visited, note_by_id = _structural_traversal(
        global_engine, zettel_id,
        reverse=True, max_depth=max_depth, node_budget=node_budget,
    )
    _emit_traversal(
        start, zettel_id, visited, note_by_id,
        as_json=as_json,
        empty_msg=f"No descendants found for {zettel_id!r}.",
    )


__all__ = ["graph"]
