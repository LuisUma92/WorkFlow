"""workflow topic CLI group — add, list, show, import."""
from __future__ import annotations

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.importer.cli import run_import
from workflow.topic.formatters import (
    format_topic_json,
    format_topic_list_json,
    format_topic_list_table,
)
from workflow.topic.service import (
    DisciplineAreaNotFound,
    DuplicateTopic,
    add_topic,
    get_topic,
    list_topics,
)

__all__ = ["topic"]

_get_engine = get_engine_from_ctx


@click.group()
def topic() -> None:
    """Manage Topic entries (GlobalBase)."""


@topic.command(name="add")
@click.option("--discipline-area", "discipline_area_code", required=True,
              help="DisciplineArea code (e.g. 0001MM).")
@click.option("--name", "name", required=True, help="Topic name.")
@click.option("--serial", "serial_number", required=True, type=int,
              help="Serial number within the discipline area.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_add(
    ctx: click.Context,
    discipline_area_code: str,
    name: str,
    serial_number: int,
    as_json: bool,
) -> None:
    """Create a new topic."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            t = add_topic(
                session,
                discipline_area_code=discipline_area_code,
                name=name,
                serial_number=serial_number,
            )
            session.commit()
            session.refresh(t)
        except DisciplineAreaNotFound as exc:
            raise click.ClickException(str(exc))
        except DuplicateTopic as exc:
            raise click.UsageError(str(exc))

        if as_json:
            click.echo(format_topic_json(t))
        else:
            click.echo(f"Created topic: {t.name!r} (id={t.id}, serial={t.serial_number})")


@topic.command(name="list")
@click.option("--discipline-area", "discipline_area_code", default=None,
              help="Filter by DisciplineArea code.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_list(
    ctx: click.Context,
    discipline_area_code: str | None,
    as_json: bool,
) -> None:
    """List topic entries."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            topics = list_topics(session, discipline_area_code=discipline_area_code)
        except DisciplineAreaNotFound as exc:
            raise click.ClickException(str(exc))

        if as_json:
            click.echo(format_topic_list_json(topics))
        else:
            click.echo(format_topic_list_table(topics))


@topic.command(name="show")
@click.argument("topic_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_show(ctx: click.Context, topic_id: int, as_json: bool) -> None:
    """Show a single topic by ID."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        t = get_topic(session, topic_id)
        if t is None:
            raise click.ClickException(f"Topic id={topic_id} not found.")

        if as_json:
            click.echo(format_topic_json(t))
        else:
            click.echo(format_topic_list_table([t]))


@topic.command(name="import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--discipline-area", "discipline_area_code", default=None,
              help="Override discipline_area_code in the file.")
@click.option("--dry-run", "dry_run", is_flag=True,
              help="Validate + report without writing.")
@click.option("--json", "as_json", is_flag=True, help="JSON summary output.")
@click.pass_context
@with_schema_guard
def cmd_import(
    ctx: click.Context,
    file: str,
    discipline_area_code: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    """[DEPRECATED] Use `workflow import`. Bulk-import a hierarchy from YAML."""
    click.echo(
        "[DEPRECATED] 'workflow topic import' is deprecated; "
        "use 'workflow import' instead.",
        err=True,
    )
    run_import(ctx, file, discipline_area_code, dry_run, as_json)
