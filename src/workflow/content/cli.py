"""workflow content CLI group — add, list, show."""
from __future__ import annotations

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.content.formatters import (
    format_content_json,
    format_content_list_json,
    format_content_list_table,
)
from workflow.content.service import (
    DuplicateContent,
    TopicNotFound,
    add_content,
    get_content,
    list_contents,
)

__all__ = ["content"]

_get_engine = get_engine_from_ctx


@click.group()
def content() -> None:
    """Manage Content entries (GlobalBase)."""


@content.command(name="add")
@click.option("--topic-id", "topic_id", required=True, type=click.IntRange(min=1),
              help="Numeric FK to Topic.id.")
@click.option("--name", "name", required=True, help="Content name.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_add(
    ctx: click.Context,
    topic_id: int,
    name: str,
    as_json: bool,
) -> None:
    """Create a new content entry."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            c = add_content(session, topic_id=topic_id, name=name)
            session.commit()
            session.refresh(c)
        except TopicNotFound as exc:
            raise click.ClickException(str(exc))
        except DuplicateContent as exc:
            raise click.UsageError(str(exc))

        if as_json:
            click.echo(format_content_json(c))
        else:
            click.echo(f"Created content: {c.name!r} (id={c.id}, topic_id={c.topic_id})")


@content.command(name="list")
@click.option("--topic-id", "topic_id", default=None, type=int,
              help="Filter by Topic.id.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_list(
    ctx: click.Context,
    topic_id: int | None,
    as_json: bool,
) -> None:
    """List content entries."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        contents = list_contents(session, topic_id=topic_id)

        if as_json:
            click.echo(format_content_list_json(contents))
        else:
            click.echo(format_content_list_table(contents))


@content.command(name="show")
@click.argument("content_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_show(ctx: click.Context, content_id: int, as_json: bool) -> None:
    """Show a single content entry by ID."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        c = get_content(session, content_id)
        if c is None:
            raise click.ClickException(f"Content id={content_id} not found.")

        if as_json:
            click.echo(format_content_json(c))
        else:
            click.echo(format_content_list_table([c]))
