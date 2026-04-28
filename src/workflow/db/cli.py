"""Database CLI — schema migrations and reference data tools."""

from __future__ import annotations

import re

import click

from workflow.db.engine import get_engine_from_ctx
from workflow.db.migrations import itep_0008 as itep_0008_migration


_PROJECT_INITIALS_RE = re.compile(r"^[A-Z]{2}$")


def _project_initials(value: str) -> str:
    upper = value.strip().upper()
    if not _PROJECT_INITIALS_RE.match(upper):
        raise click.BadParameter("must be exactly two uppercase letters (A-Z).")
    return upper


@click.group("db")
def db() -> None:
    """Manage the WorkFlow global database (schema, seeds, migrations)."""


@db.group("migrate")
def migrate() -> None:
    """Apply schema migrations to the global database."""


@migrate.command("itep-0008")
@click.option(
    "--backfill-nuclear-physics",
    is_flag=True,
    default=False,
    help=(
        "Create area MainTopic 0060NP if absent and prompt for the three "
        "Nuclear Physics children (year_init, project_initials, title)."
    ),
)
@click.pass_context
def migrate_itep_0008(ctx: click.Context, backfill_nuclear_physics: bool) -> None:
    """Apply ITEP-0008 schema migration (idempotent)."""
    engine = get_engine_from_ctx(ctx)

    backfill: itep_0008_migration.BackfillRequest | None = None
    if backfill_nuclear_physics:
        children: list[tuple[str, int, str, str]] = []
        click.echo(
            "Provide each child MainTopic code currently representing a "
            "Nuclear Physics project. Leave the code blank to stop."
        )
        while True:
            code = click.prompt("child code", default="", show_default=False)
            if not code:
                break
            yy = click.prompt("  year_init (YY 0-99)", type=click.IntRange(0, 99))
            pp = click.prompt(
                "  project_initials (2 uppercase letters)",
                value_proc=_project_initials,
            )
            title = click.prompt("  title", type=str)
            children.append((code, yy, pp, title))
        backfill = itep_0008_migration.BackfillRequest(
            area_code="0060NP",
            area_name="Nuclear Physics",
            children=tuple(children),
        )

    report = itep_0008_migration.run_migration(engine, backfill=backfill)

    click.echo("ITEP-0008 migration complete.")
    if report.columns_added:
        click.echo(f"  columns added:        {', '.join(report.columns_added)}")
    if report.tables_created:
        click.echo(f"  tables created:       {', '.join(report.tables_created)}")
    if report.areas_created:
        click.echo(f"  areas created:        {', '.join(report.areas_created)}")
    if report.children_reassigned:
        click.echo(f"  children reassigned:  {', '.join(report.children_reassigned)}")
    if report.projects_backfilled:
        click.echo(f"  projects backfilled:  {', '.join(report.projects_backfilled)}")
    if not any(
        (
            report.columns_added,
            report.tables_created,
            report.areas_created,
            report.children_reassigned,
            report.projects_backfilled,
        )
    ):
        click.echo("  (no changes — already up to date)")
