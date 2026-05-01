"""Database CLI — schema migrations and reference data tools."""

from __future__ import annotations

from pathlib import Path

import click
from sqlalchemy.orm import Session

import json as _json

from workflow.db import migrations, seed_codes, taxonomy
from workflow.db.engine import get_engine_from_ctx
from workflow.db.schema_version import applied_revisions, current_version


@click.group("db")
def db() -> None:
    """Manage the WorkFlow global database (schema, seeds, migrations)."""


@db.group(
    "migrate",
    invoke_without_command=True,
    help="Apply pending schema migrations (ITEP-0010).",
)
@click.option(
    "--base",
    type=click.Choice(["global", "local", "all"], case_sensitive=False),
    default="global",
    show_default=True,
    help="Which database base to operate on.",
)
@click.option(
    "--to",
    "to_revision",
    type=str,
    default=None,
    help="Apply migrations up to and including this revision.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would run without modifying the database.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON instead of human text.",
)
@click.pass_context
def migrate(
    ctx: click.Context,
    base: str,
    to_revision: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Apply pending migrations. With no subcommand, runs the upgrade."""
    if ctx.invoked_subcommand is not None:
        ctx.obj = ctx.obj or {}
        ctx.obj["migrate_base"] = base
        return

    engine = get_engine_from_ctx(ctx)
    bases = ["global", "local"] if base == "all" else [base]

    payload: dict[str, dict] = {}
    for b in bases:
        result = migrations.upgrade(engine, b, to=to_revision, dry_run=dry_run)
        payload[b] = result.to_dict()

    if as_json:
        if len(payload) == 1:
            click.echo(
                _json.dumps(next(iter(payload.values())), ensure_ascii=False, indent=2)
            )
        else:
            click.echo(_json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for b, p in payload.items():
        prefix = "[dry-run] " if dry_run else ""
        click.echo(f"{prefix}base={b} head={p['head']}")
        if p["applied"]:
            click.echo(f"  applied:  {', '.join(p['applied'])}")
        if p["skipped"]:
            click.echo(f"  skipped:  {', '.join(p['skipped'])}")
        if not p["applied"] and not p["skipped"]:
            click.echo("  (no migrations discovered)")


@migrate.command("status")
@click.option(
    "--base",
    type=click.Choice(["global", "local", "all"], case_sensitive=False),
    default="global",
    show_default=True,
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
)
@click.pass_context
def migrate_status(ctx: click.Context, base: str, as_json: bool) -> None:
    """Show current head and applied revisions per base."""
    engine = get_engine_from_ctx(ctx)
    bases = ["global", "local"] if base == "all" else [base]

    payload: dict[str, dict] = {}
    for b in bases:
        # Ensure schema_version table exists for read-only inspection.
        from workflow.db.schema_version import model_for

        model_for(b).__table__.create(engine, checkfirst=True)
        with Session(engine) as s:
            payload[b] = {
                "head": current_version(s, b),
                "applied": applied_revisions(s, b),
            }

    if as_json:
        # Single-base query collapses the wrapper for ergonomics.
        if len(payload) == 1:
            click.echo(
                _json.dumps(next(iter(payload.values())), ensure_ascii=False, indent=2)
            )
        else:
            click.echo(_json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for b, p in payload.items():
        click.echo(f"base={b} head={p['head']}")
        if p["applied"]:
            click.echo(f"  applied: {', '.join(p['applied'])}")


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


@db.group("taxonomy")
def taxonomy_group() -> None:
    """Read-only access to the discipline taxonomy (ADR ITEP-0009 Part I)."""


@taxonomy_group.command("list")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON instead of a table.",
)
@click.option(
    "--data-dir",
    "data_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Override the directory scanned for DD-*Codes.csv.",
)
def taxonomy_list(as_json: bool, data_dir: Path | None) -> None:
    """List the registered disciplines and their bundled CSV files."""
    entries = taxonomy.discover_disciplines(data_dir)
    if as_json:
        click.echo(
            _json.dumps(
                [
                    {
                        "dd": e.dd,
                        "code_prefix": e.code_prefix,
                        "name": e.name,
                        "csv": str(e.csv_path) if e.csv_path else None,
                        "hobby": e.hobby,
                    }
                    for e in entries
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    click.echo("DD  Discipline                       Hobby  CSV")
    click.echo("--  -------------------------------  -----  ---")
    for e in entries:
        csv_label = e.csv_path.name if e.csv_path else "(missing)"
        hobby_flag = "yes" if e.hobby else "no"
        click.echo(f"{e.code_prefix}  {e.name:<31}  {hobby_flag:<5}  {csv_label}")
