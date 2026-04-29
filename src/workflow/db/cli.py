"""Database CLI — schema migrations and reference data tools."""

from __future__ import annotations

import re
from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db import seed_codes
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


def _print_upsert_report(report: seed_codes.UpsertReport) -> None:
    if report.inserted:
        click.echo(f"  inserted ({len(report.inserted)}): {', '.join(report.inserted)}")
    if report.updated:
        click.echo(f"  updated  ({len(report.updated)}): {', '.join(report.updated)}")
    if report.unchanged:
        click.echo(f"  unchanged: {len(report.unchanged)}")
    if report.skipped:
        click.echo(f"  skipped ({len(report.skipped)}):")
        for lineno, reason in report.skipped:
            click.echo(f"    line {lineno}: {reason}")
    if not report.changed and not report.skipped:
        click.echo("  (no changes — already up to date)")


@db.command("import-codes")
@click.option(
    "--csv",
    "csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Import a single discipline-codes CSV file.",
)
@click.option(
    "--all",
    "import_all",
    is_flag=True,
    default=False,
    help="Import every DD-*Codes.csv in the bundled data/ directory.",
)
@click.option(
    "--data-dir",
    "data_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Override the directory scanned by --all (defaults to repo data/).",
)
@click.pass_context
def import_codes(
    ctx: click.Context,
    csv_path: Path | None,
    import_all: bool,
    data_dir: Path | None,
) -> None:
    """UPSERT discipline-area codes from CSV into the global database."""
    if csv_path is None and not import_all:
        raise click.UsageError("specify --csv PATH or --all.")
    if csv_path is not None and import_all:
        raise click.UsageError("--csv and --all are mutually exclusive.")

    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        if csv_path is not None:
            click.echo(f"Importing {csv_path.name}…")
            report = seed_codes.upsert_from_csv(session, csv_path)
        else:
            target = data_dir or seed_codes.default_data_dir()
            click.echo(f"Importing all *Codes.csv from {target}…")
            report = seed_codes.upsert_all_csvs(session, target)

    _print_upsert_report(report)
