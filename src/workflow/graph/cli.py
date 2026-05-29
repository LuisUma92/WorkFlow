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
from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.errors import with_schema_guard
from workflow.graph.analysis import compute_stats, find_orphans, neighbors
from workflow.graph.collectors import (
    TaxonomyFilter,
    build_knowledge_graph,
    filter_graph_by_taxonomy,
    resolve_taxonomy_filter,
)
from workflow.graph.domain import KnowledgeGraph


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
) -> KnowledgeGraph:
    """Build + filter the knowledge graph in a single DB session."""
    del project  # reserved for ITEP-0011 P5 routing
    global_engine = init_global_db()
    with Session(global_engine) as gsession:
        tf = _resolve_filter(gsession, main_topic, discipline_area, topic)
        kg = build_knowledge_graph(gsession)
        if not tf.is_empty():
            kg = filter_graph_by_taxonomy(kg, gsession, tf)
        return kg


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
    """List nodes with no connections."""
    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)
    orphan_nodes = find_orphans(kg, node_type=node_type)

    if as_json:
        click.echo(
            _json.dumps(
                [
                    {"node_id": n.node_id, "node_type": n.node_type, "label": n.label}
                    for n in orphan_nodes
                ]
            )
        )
        return

    if not orphan_nodes:
        click.echo("No orphaned nodes found.")
        return

    for node in orphan_nodes:
        click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}")
    click.echo(f"\nTotal: {len(orphan_nodes)} orphan(s).")


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
@_filter_options
@with_schema_guard
def export_tikz_cmd(
    project: str,
    output: str | None,
    standalone: bool,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Export graph as TikZ for LaTeX rendering."""
    from workflow.graph.tikz_export import graph_to_tikz

    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)
    tikz = graph_to_tikz(kg, standalone=standalone)

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


# ── neighbors ────────────────────────────────────────────────────────────────


@graph.command(name="neighbors")
@click.argument("node_id")
@click.option("--depth", default=1, help="Hop distance.")
@click.option("--project", type=click.Path(exists=True), default=".")
@_filter_options
@with_schema_guard
def neighbors_cmd(
    node_id: str,
    depth: int,
    project: str,
    main_topic: str | None,
    discipline_area: str | None,
    topic: str | None,
) -> None:
    """Show neighbours of a node."""
    kg = _build_graph_with_filter(project, main_topic, discipline_area, topic)

    if node_id not in kg.node_ids():
        raise click.ClickException(f"Node not found: {node_id}")

    subgraph = neighbors(kg, node_id, depth=depth)

    for node in subgraph.nodes:
        marker = " *" if node.node_id == node_id else ""
        click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}{marker}")
    click.echo(f"\n{len(subgraph.nodes)} node(s), {len(subgraph.edges)} edge(s).")


__all__ = ["graph"]
