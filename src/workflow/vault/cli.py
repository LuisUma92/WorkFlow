"""Workflow vault CLI — ITEP-0011 P2.

Commands:
    workflow vault info
    workflow vault validate
    workflow vault unify [...]
"""

from __future__ import annotations

import os
from pathlib import Path

import click

from sqlalchemy.orm import sessionmaker

from workflow.db.engine import init_global_db
from workflow.db.errors import with_schema_guard
from workflow.vault.paths import (
    DEFAULT_VAULT_ROOT,
    ENV_VAULT_ROOT,
    resolve_vault_root,
)
from workflow.vault.unify import (
    NOTE_TYPES,
    VAULT_POINTER_FILE,
    unify as unify_logic,
)

__all__ = ["vault", "resolve_vault_root", "DEFAULT_VAULT_ROOT", "ENV_VAULT_ROOT"]


@click.group()
def vault() -> None:
    """Unified Zettelkasten vault management (ITEP-0011)."""


@vault.command(name="info")
def info_cmd() -> None:
    """Print resolved vault root and structure status."""
    root = resolve_vault_root()
    click.echo(f"vault_root: {root}")
    click.echo(
        f"source: {'env ' + ENV_VAULT_ROOT if os.environ.get(ENV_VAULT_ROOT) else 'default'}"
    )
    click.echo(f"exists: {root.exists()}")
    if root.exists():
        for sub in NOTE_TYPES:
            d = root / "notes" / sub
            click.echo(f"  notes/{sub}: {'OK' if d.is_dir() else 'MISSING'}")


@vault.command(name="validate")
@click.option("--vault-root", type=click.Path(path_type=Path), default=None)
def validate_cmd(vault_root: Path | None) -> None:
    """Verify vault structure (notes/{permanent,literature,fleeting})."""
    root = vault_root.resolve() if vault_root else resolve_vault_root()
    if not root.is_dir():
        raise click.ClickException(f"vault_root not found: {root}")
    missing = [s for s in NOTE_TYPES if not (root / "notes" / s).is_dir()]
    if missing:
        raise click.ClickException(
            f"missing subdirs in {root}/notes: {', '.join(missing)}"
        )
    click.echo(f"OK — {root}")


@vault.command(name="unify")
@click.option(
    "--project-root",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Absolute path to the project directory.",
)
@click.option("--vault-root", type=click.Path(path_type=Path), default=None)
@click.option("--backup-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--rename-strategy",
    type=click.Choice(["project-prefix", "abort", "manual"]),
    default="abort",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    help="Default dry-run; pass --no-dry-run to commit.",
)
@with_schema_guard
def unify_cmd(
    project_root: Path,
    vault_root: Path | None,
    backup_dir: Path | None,
    rename_strategy: str,
    dry_run: bool,
) -> None:
    """Migrate a project's slipbox.db notes into the global vault."""
    project_root = project_root.resolve()
    root = vault_root.resolve() if vault_root else resolve_vault_root()
    if not root.is_dir():
        raise click.ClickException(f"vault_root not found: {root}")
    bdir = (
        backup_dir.resolve()
        if backup_dir
        else (Path.home() / ".local" / "share" / "workflow" / "vault-backups")
    )

    engine = init_global_db()
    Session = sessionmaker(bind=engine)
    with Session() as session:
        try:
            report = unify_logic(
                project_root,
                root,
                backup_dir=bdir,
                global_session=session,
                rename_strategy=rename_strategy,  # type: ignore[arg-type]
                dry_run=dry_run,
            )
            if not dry_run:
                session.commit()
        except ValueError as exc:
            session.rollback()
            raise click.ClickException(str(exc)) from exc

    _print_report(report, dry_run=dry_run)

    if report.skipped_collisions and not dry_run:
        raise click.ClickException(
            f"{len(report.skipped_collisions)} collisions skipped under "
            f"--rename-strategy={rename_strategy}; first: "
            f"{report.skipped_collisions[0]!r}. Re-run with "
            "--rename-strategy=project-prefix to migrate them."
        )


def _print_report(report, *, dry_run: bool) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    if report.skipped:
        click.echo(f"{prefix}skipped: {report.skip_reason}")
        return
    click.echo(f"{prefix}project: {report.project_name}")
    click.echo(f"  notes:     {report.notes_migrated}")
    click.echo(f"  labels:    {report.labels_migrated}")
    click.echo(f"  links:     {report.links_migrated}")
    click.echo(f"  citations: {report.citations_migrated}")
    click.echo(f"  tags:      {report.tags_migrated}")
    click.echo(f"  note_tags: {report.note_tags_migrated}")
    click.echo(f"  files:     {report.files_moved}")
    if report.collisions:
        click.echo(
            f"  collisions ({len(report.collisions)}): "
            f"{report.collisions[:3]}{'...' if len(report.collisions) > 3 else ''}"
        )
    if report.orphans:
        click.echo(f"  orphan links: {len(report.orphans)}")
    if report.backup_path:
        click.echo(f"  backup: {report.backup_path}")
