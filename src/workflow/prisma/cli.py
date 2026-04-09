"""PRISMA systematic review CLI commands.

Click command groups wired into the main ``workflow`` CLI.
Groups: ``prisma`` with subgroups ``bib``, ``keyword``, ``review``.
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
    format_keyword_json,
    format_keyword_table,
    format_review_json,
    format_review_table,
)
from workflow.prisma.service import (
    get_bib_detail,
    list_bib_entries,
    list_keywords,
    list_reviews,
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
