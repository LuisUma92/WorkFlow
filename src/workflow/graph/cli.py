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

from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_local_engine, init_global_db
from workflow.graph.analysis import compute_stats, find_orphans, neighbors
from workflow.graph.collectors import build_knowledge_graph
from workflow.graph.domain import KnowledgeGraph


# ── Graph builder ───────────────────────────────────────────────────────────


def _build_graph(project: str) -> KnowledgeGraph:
    """Build knowledge graph from global + optional local DB."""
    global_engine = init_global_db()
    project_path = Path(project)
    local_db = project_path / "slipbox.db"

    with Session(global_engine) as gsession:
        if local_db.exists():
            local_engine = get_local_engine(project_path)
            with Session(local_engine) as lsession:
                return build_knowledge_graph(gsession, lsession)
        else:
            return build_knowledge_graph(gsession)


# ── CLI group ───────────────────────────────────────────────────────────────


@click.group()
def graph() -> None:
    """Knowledge graph analysis and export."""


# ── orphans ─────────────────────────────────────────────────────────────────


@graph.command()
@click.option(
    "--type", "node_type",
    type=click.Choice(
        ["note", "exercise", "bib_entry", "content", "topic", "course"],
        case_sensitive=False,
    ),
    default=None,
    help="Filter orphans by node type.",
)
@click.option("--project", type=click.Path(exists=True), default=".")
def orphans(node_type: str | None, project: str) -> None:
    """List nodes with no connections."""
    kg = _build_graph(project)
    orphan_nodes = find_orphans(kg, node_type=node_type)

    if not orphan_nodes:
        click.echo("No orphaned nodes found.")
        return

    for node in orphan_nodes:
        click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}")
    click.echo(f"\nTotal: {len(orphan_nodes)} orphan(s).")


# ── stats ────────────────────────────────────────────────────────────────────


@graph.command()
@click.option("--project", type=click.Path(exists=True), default=".")
def stats(project: str) -> None:
    """Show graph summary statistics."""
    kg = _build_graph(project)
    s = compute_stats(kg)

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
def export_dot_cmd(project: str, output: str | None, highlight_orphans: bool) -> None:
    """Export graph as Graphviz DOT."""
    from workflow.graph.dot_export import graph_to_dot

    kg = _build_graph(project)
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
def export_tikz_cmd(project: str, output: str | None, standalone: bool) -> None:
    """Export graph as TikZ for LaTeX rendering."""
    from workflow.graph.tikz_export import graph_to_tikz

    kg = _build_graph(project)
    tikz = graph_to_tikz(kg, standalone=standalone)

    if output:
        Path(output).write_text(tikz, encoding="utf-8")
        click.echo(f"TikZ exported to {output}")
    else:
        click.echo(tikz)


# ── clusters ─────────────────────────────────────────────────────────────────


@graph.command()
@click.option("--project", type=click.Path(exists=True), default=".")
def clusters(project: str) -> None:
    """Show topic clusters (requires networkx)."""
    from workflow.graph.clustering import detect_communities

    kg = _build_graph(project)
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
def neighbors_cmd(node_id: str, depth: int, project: str) -> None:
    """Show neighbours of a node."""
    kg = _build_graph(project)

    if node_id not in kg.node_ids():
        raise click.ClickException(f"Node not found: {node_id}")

    subgraph = neighbors(kg, node_id, depth=depth)

    for node in subgraph.nodes:
        marker = " *" if node.node_id == node_id else ""
        click.echo(f"  [{node.node_type}] {node.node_id}: {node.label}{marker}")
    click.echo(f"\n{len(subgraph.nodes)} node(s), {len(subgraph.edges)} edge(s).")


__all__ = ["graph"]
