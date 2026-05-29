"""workflow content CLI group — add, list, show."""
from __future__ import annotations

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.content.formatters import (
    format_bib_link_json,
    format_bib_link_list_json,
    format_bib_link_list_table,
    format_content_json,
    format_content_list_json,
    format_content_list_table,
)
from workflow.content.service import (
    BibEntryNotFound,
    BibKeyAmbiguous,
    BibLinkAlreadyExists,
    BibLinkNotFound,
    ContentNotFound,
    DuplicateContent,
    TopicNotFound,
    add_content,
    get_content,
    link_bib_to_content,
    list_bib_links,
    list_contents,
    unlink_bib_from_content,
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


@content.command(name="link-bib")
@click.option("--content-id", "content_id", required=True, type=click.IntRange(min=1),
              help="Numeric FK to Content.id.")
@click.option("--bibkey", required=True, help="BibEntry bibkey string.")
@click.option("--chapter", "chapter_number", required=True, type=int,
              help="Chapter number.")
@click.option("--section", "section_number", required=True, type=int,
              help="Section number.")
@click.option("--first-page", "first_page", required=True, type=int,
              help="First page.")
@click.option("--last-page", "last_page", required=True, type=int,
              help="Last page.")
@click.option("--first-exercise", "first_exercise", default=None, type=int,
              help="First exercise number (optional).")
@click.option("--last-exercise", "last_exercise", default=None, type=int,
              help="Last exercise number (optional).")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_link_bib(
    ctx: click.Context,
    content_id: int,
    bibkey: str,
    chapter_number: int,
    section_number: int,
    first_page: int,
    last_page: int,
    first_exercise: int | None,
    last_exercise: int | None,
    as_json: bool,
) -> None:
    """Link a BibEntry (by bibkey) to a Content entry."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            bc = link_bib_to_content(
                session,
                content_id=content_id,
                bibkey=bibkey,
                chapter_number=chapter_number,
                section_number=section_number,
                first_page=first_page,
                last_page=last_page,
                first_exercise=first_exercise,
                last_exercise=last_exercise,
            )
            session.commit()
            session.refresh(bc)
            _ = bc.bib_entry  # materialise relationship while session is open
        except (BibEntryNotFound, ContentNotFound, BibKeyAmbiguous) as exc:
            raise click.ClickException(str(exc))
        except BibLinkAlreadyExists as exc:
            raise click.UsageError(str(exc))

        if as_json:
            click.echo(format_bib_link_json(bc))
        else:
            bk = bc.bib_entry.bibkey if bc.bib_entry else bibkey
            click.echo(
                f"Linked bibkey={bk!r} to content id={content_id} "
                f"(ch={chapter_number}, sec={section_number}, "
                f"pages={first_page}-{last_page})"
            )


@content.command(name="bib-links")
@click.option("--content-id", "content_id", required=True, type=click.IntRange(min=1),
              help="Numeric FK to Content.id.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_bib_links(ctx: click.Context, content_id: int, as_json: bool) -> None:
    """List BibEntry links for a content entry."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        links = list_bib_links(session, content_id=content_id)

        if as_json:
            click.echo(format_bib_link_list_json(links))
        else:
            click.echo(format_bib_link_list_table(links))


@content.command(name="unlink-bib")
@click.option("--content-id", "content_id", required=True, type=click.IntRange(min=1),
              help="Numeric FK to Content.id.")
@click.option("--bibkey", required=True, help="BibEntry bibkey string.")
@click.pass_context
@with_schema_guard
def cmd_unlink_bib(ctx: click.Context, content_id: int, bibkey: str) -> None:
    """Remove the link between a BibEntry (by bibkey) and a Content entry."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            unlink_bib_from_content(session, content_id=content_id, bibkey=bibkey)
            session.commit()
        except (BibEntryNotFound, BibKeyAmbiguous, BibLinkNotFound) as exc:
            raise click.ClickException(str(exc))

        click.echo(f"Unlinked bibkey={bibkey!r} from content id={content_id}.")
