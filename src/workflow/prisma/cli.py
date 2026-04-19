"""PRISMA systematic review CLI commands.

Click command groups wired into the main ``workflow`` CLI.
Groups: ``prisma`` with subgroups ``bib``, ``keyword``, ``review``, ``tag``, ``rationale``.
"""

from __future__ import annotations

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.prisma.formatters import (
    format_bib_detail_json,
    format_bib_detail_table,
    format_bib_json,
    format_bib_table,
    format_import_result_json,
    format_import_result_table,
    format_keyword_json,
    format_keyword_table,
    format_rationale_json,
    format_rationale_table,
    format_review_json,
    format_review_table,
    format_tag_json,
    format_tag_table,
)
from workflow.prisma.importer import import_bib_file
from workflow.prisma.service import (
    REVIEW_STATUS_LABELS,
    create_keyword,
    create_rationale,
    create_tag,
    get_bib_detail,
    list_bib_entries,
    list_keywords,
    list_rationales,
    list_reviews,
    list_tags,
    screen_article,
    search_bib_entries,
)

__all__ = ["prisma"]


# ── prisma group ─────────────────────────────────────────────────────────


@click.group()
def prisma() -> None:
    """PRISMA systematic review management."""


# ── bib subgroup ─────────────────────────────────────────────────────────


@prisma.group()
def bib() -> None:
    """Bibliography entry management."""


@bib.command(name="list")
@click.option("--year", type=int, default=None, help="Filter by publication year.")
@click.option("--type", "entry_type", default=None, help="Filter by entry type.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def bib_list(
    ctx: click.Context, year: int | None, entry_type: str | None, as_json: bool
) -> None:
    """List bibliography entries."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        entries = list_bib_entries(session, year=year, entry_type=entry_type)

        if as_json:
            click.echo(format_bib_json(entries))
        else:
            click.echo(format_bib_table(entries))


@bib.command(name="show")
@click.argument("bib_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def bib_show(ctx: click.Context, bib_id: int, as_json: bool) -> None:
    """Show a single bibliography entry with full detail."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        entry = get_bib_detail(session, bib_id)

        if entry is None:
            raise click.ClickException(f"BibEntry with id={bib_id} not found.")

        if as_json:
            click.echo(format_bib_detail_json(entry))
        else:
            click.echo(format_bib_detail_table(entry))


@bib.command(name="search")
@click.option("--title", default=None, help="Search by title (case-insensitive).")
@click.option("--author", default=None, help="Search by author name.")
@click.option("--year", type=int, default=None, help="Filter by year.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def bib_search(
    ctx: click.Context,
    title: str | None,
    author: str | None,
    year: int | None,
    as_json: bool,
) -> None:
    """Search bibliography entries by title, author, and/or year."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        try:
            entries = search_bib_entries(session, title=title, author=author, year=year)
        except ValueError as e:
            raise click.ClickException(str(e))

        if as_json:
            click.echo(format_bib_json(entries))
        else:
            click.echo(format_bib_table(entries))


@bib.command(name="import")
@click.argument(
    "path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option(
    "--database-name",
    default=None,
    help="Source database label (e.g., 'PubMed'). Inferred from filename prefix if omitted.",
)
@click.option("--verbose", is_flag=True, help="Print per-entry status.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def bib_import(
    ctx: click.Context,
    path: str,
    database_name: str | None,
    verbose: bool,
    as_json: bool,
) -> None:
    """Import a BibTeX file into the bibliography."""
    engine = get_engine_from_ctx(ctx)

    try:
        with Session(engine) as session:
            result = import_bib_file(session, path, database_name=database_name)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(format_import_result_json(result))
    else:
        click.echo(format_import_result_table(result, verbose=verbose))


# ── keyword subgroup ─────────────────────────────────────────────────────


@prisma.group()
def keyword() -> None:
    """Search keyword management."""


@keyword.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def keyword_list(ctx: click.Context, as_json: bool) -> None:
    """List search keywords."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        keywords = list_keywords(session)

        if as_json:
            click.echo(format_keyword_json(keywords))
        else:
            click.echo(format_keyword_table(keywords))


@keyword.command(name="add")
@click.option("--text", required=True, help="Keyword text.")
@click.pass_context
def keyword_add(ctx: click.Context, text: str) -> None:
    """Create a new search keyword."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        try:
            kw = create_keyword(session, text=text)
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(f"Created keyword: '{kw.keyword_list}' (id={kw.id})")


# ── tag subgroup ─────────────────────────────────────────────────────────


@prisma.group()
def tag() -> None:
    """Article tag management."""


@tag.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def tag_list(ctx: click.Context, as_json: bool) -> None:
    """List tags."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        tags = list_tags(session)

        if as_json:
            click.echo(format_tag_json(tags))
        else:
            click.echo(format_tag_table(tags))


@tag.command(name="add")
@click.option("--text", required=True, help="Tag text.")
@click.pass_context
def tag_add(ctx: click.Context, text: str) -> None:
    """Create a new tag."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        try:
            t = create_tag(session, text=text)
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(f"Created tag: '{t.tag}' (id={t.id})")


# ── rationale subgroup ───────────────────────────────────────────────────


@prisma.group()
def rationale() -> None:
    """Rationale option management."""


@rationale.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def rationale_list(ctx: click.Context, as_json: bool) -> None:
    """List rationale options."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        rationales = list_rationales(session)

        if as_json:
            click.echo(format_rationale_json(rationales))
        else:
            click.echo(format_rationale_table(rationales))


@rationale.command(name="add")
@click.option("--text", required=True, help="Rationale argument text.")
@click.pass_context
def rationale_add(ctx: click.Context, text: str) -> None:
    """Create a new rationale option."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        try:
            opt = create_rationale(session, text=text)
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(f"Created rationale: '{opt.rationale_argument}' (id={opt.id})")


# ── review subgroup ──────────────────────────────────────────────────────


@prisma.group()
def review() -> None:
    """Systematic review screening."""


@review.command(name="list")
@click.option("--keyword-id", required=True, type=int, help="Keyword ID to filter by.")
@click.option(
    "--status",
    type=click.Choice(["included", "excluded", "pending"], case_sensitive=False),
    default=None,
    help="Filter by review status.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def review_list(
    ctx: click.Context, keyword_id: int, status: str | None, as_json: bool
) -> None:
    """List review records for a keyword."""
    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        try:
            records, kw = list_reviews(session, keyword_id=keyword_id, status=status)
        except ValueError as e:
            raise click.ClickException(str(e))

        if as_json:
            click.echo(format_review_json(records))
        else:
            click.echo(format_review_table(records, keyword_text=kw.keyword_list))


@review.command(name="screen")
@click.argument("bib_id", type=int)
@click.option("--keyword-id", required=True, type=int, help="Keyword ID.")
@click.option("--include", "decision", flag_value="include", help="Mark as included.")
@click.option("--exclude", "decision", flag_value="exclude", help="Mark as excluded.")
@click.option("--rationale", default=None, help="Rationale text.")
@click.pass_context
def review_screen(
    ctx: click.Context,
    bib_id: int,
    keyword_id: int,
    decision: str | None,
    rationale: str | None,
) -> None:
    """Screen an article for a keyword (include or exclude)."""
    if decision is None:
        raise click.ClickException("Specify --include or --exclude.")

    engine = get_engine_from_ctx(ctx)

    with Session(engine) as session:
        try:
            rec = screen_article(
                session,
                bib_entry_id=bib_id,
                keyword_id=keyword_id,
                include=(decision == "include"),
                rationale=rationale,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        status_label = REVIEW_STATUS_LABELS.get(rec.included, "unknown")
        click.echo(
            f"Screened bib_entry id={bib_id} as {status_label} "
            f"for keyword id={keyword_id} (review id={rec.id})"
        )
