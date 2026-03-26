"""Notes CLI — Zettelkasten note management commands."""

from __future__ import annotations

from pathlib import Path

import click

from workflow.notes.init import init_workspace

__all__ = ["notes"]


@click.group()
def notes() -> None:
    """Zettelkasten note management."""


@notes.command(name="init")
@click.argument("workspace", type=click.Path(), default=".")
def init_cmd(workspace: str) -> None:
    """Initialize a WorkFlow workspace with note directories."""
    workspace_path = Path(workspace).resolve()

    if not workspace_path.exists():
        raise click.ClickException(f"Directory does not exist: {workspace_path}")

    result = init_workspace(workspace_path)

    if result.directories_created:
        click.echo("Created:")
        for d in result.directories_created:
            click.echo(f"  + {d}")

    if result.projects_initialized:
        click.echo(f"\nProjects initialized ({len(result.projects_initialized)}):")
        for p in result.projects_initialized:
            click.echo(f"  + {p}/slipbox.db")

    if result.already_existed and not result.directories_created:
        click.echo("Workspace already initialized — nothing to do.")

    for w in result.warnings:
        click.echo(f"  [WARN] {w}")
