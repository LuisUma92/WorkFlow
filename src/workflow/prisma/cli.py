"""PRISMA systematic review CLI commands.

Click command groups wired into the main ``workflow`` CLI.
Groups: ``prisma`` with subgroups ``bib``, ``keyword``, ``review``, ``tag``, ``rationale``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.prisma.formatters import (
    format_bib_detail_json,
    format_bib_detail_table,
    format_bib_json,
    format_bib_table,
    format_checklist_json,
    format_checklist_table,
    format_import_result_json,
    format_import_result_table,
    format_keyword_json,
    format_keyword_table,
    format_rationale_json,
    format_rationale_table,
    format_recompute_json,
    format_recompute_table,
    format_review_json,
    format_review_table,
    format_stats_json,
    format_stats_table,
    format_tag_json,
    format_tag_table,
)
from workflow.prisma.exporter import Dialect, ReviewStatus, export_bib_entries
from workflow.prisma.importer import import_bib_file, import_bib_text
from workflow.prisma.recompute import (
    apply_recompute,
    backup_database,
    compute_recompute_plan,
)
from workflow.prisma.service import (
    REVIEW_STATUS_LABELS,
    create_keyword,
    create_rationale,
    create_tag,
    get_bib_detail,
    get_checklist,
    get_review_stats,
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
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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
    required=False,
    default=None,
    type=click.Path(dir_okay=False, readable=True),
)
@click.option("--stdin", "use_stdin", is_flag=True, help="Read biblatex from stdin instead of a file.")
@click.option(
    "--database-name",
    default=None,
    help="Source database label (e.g., 'PubMed'). Inferred from filename prefix if omitted.",
)
@click.option("--verbose", is_flag=True, help="Print per-entry status.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.option(
    "--recompute-bibkeys",
    "recompute_bibkeys",
    is_flag=True,
    default=False,
    help=(
        "Force bibkey recalculation for all imported entries, ignoring the source .bib ID. "
        "By default, source IDs are kept verbatim and only missing/empty IDs are calculated."
    ),
)
@click.pass_context
@with_schema_guard
def bib_import(
    ctx: click.Context,
    path: str | None,
    use_stdin: bool,
    database_name: str | None,
    verbose: bool,
    as_json: bool,
    recompute_bibkeys: bool,
) -> None:
    """Import a BibTeX file into the bibliography.

    Provide a file PATH, or use --stdin to read biblatex from standard input.
    """
    if use_stdin and path is not None:
        raise click.ClickException("--stdin cannot be combined with a file path")
    if not use_stdin and path is None:
        raise click.ClickException("Provide a file PATH or use --stdin to read from stdin.")

    engine = get_engine_from_ctx(ctx)

    try:
        with Session(engine) as session:
            if use_stdin:
                text = sys.stdin.read()
                result = import_bib_text(
                    session, text,
                    database_name=database_name,
                    recompute_bibkeys=recompute_bibkeys,
                )
            else:
                if not Path(path).exists():
                    raise FileNotFoundError(f"bib file not found: {path}")
                result = import_bib_file(
                    session, path,
                    database_name=database_name,
                    recompute_bibkeys=recompute_bibkeys,
                )
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(format_import_result_json(result))
    else:
        click.echo(format_import_result_table(result, verbose=verbose))


@bib.command(name="export")
@click.option("--keyword-id", type=int, default=None, help="Filter by keyword id.")
@click.option(
    "--status",
    type=click.Choice(["included", "excluded", "pending"]),
    default=None,
    help="Filter by review status (requires --keyword-id).",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Write to this file instead of stdout.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite --output if it exists.",
)
@click.option(
    "--dialect",
    type=click.Choice(["biblatex", "bibtex"], case_sensitive=False),
    default="biblatex",
    show_default=True,
    help="Output dialect: 'biblatex' (canonical) or 'bibtex' (downgraded aliases).",
)
@click.pass_context
@with_schema_guard
def bib_export(
    ctx: click.Context,
    keyword_id: int | None,
    status: str | None,
    output: str | None,
    force: bool,
    dialect: str,
) -> None:
    """Export bibliography entries as BibLaTeX or BibTeX.

    Default dialect is biblatex (canonical field names, no type downgrade).
    Use --dialect bibtex for a bibtex-compatible export with downgraded entry
    types and reversed field aliases (journaltitle→journal, etc.).
    """
    if status is not None and keyword_id is None:
        raise click.ClickException("--status requires --keyword-id")

    review_status = cast("ReviewStatus | None", status)
    export_dialect = cast("Dialect", dialect)

    engine = get_engine_from_ctx(ctx)
    try:
        with Session(engine) as session:
            bib_output = export_bib_entries(
                session,
                keyword_id=keyword_id,
                status=review_status,
                dialect=export_dialect,
            )
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if output:
        out_path = Path(output)
        if out_path.exists() and not force:
            raise click.ClickException(f"{output} exists; pass --force to overwrite.")
        out_path.write_text(bib_output, encoding="utf-8")
    else:
        click.echo(bib_output)


# ── bib recompute-keys ───────────────────────────────────────────────────


def _guard_recompute_all(*, as_json: bool, confirmed: bool) -> None:
    """Enforce the --all confirmation contract (raises on abort/missing --yes)."""
    if as_json:
        if not confirmed:
            raise click.ClickException("--all in --json mode requires --yes")
    elif not confirmed:
        click.confirm(
            "--all recomputes EVERY bibkey; keys referenced in review "
            "rationales / external .bib exports may go stale. Continue?",
            abort=True,
        )


@bib.command(name="recompute-keys")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report changes without writing or backing up.",
)
@click.option(
    "--all",
    "recompute_all",
    is_flag=True,
    help="Recompute every entry (normalize). Default fills only missing keys.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.option(
    "--yes",
    "confirmed",
    is_flag=True,
    help="Skip the --all confirmation prompt (required for --json --all).",
)
@click.pass_context
@with_schema_guard
def bib_recompute_keys(
    ctx: click.Context,
    dry_run: bool,
    recompute_all: bool,
    as_json: bool,
    confirmed: bool,
) -> None:
    """Assign or recompute calculated bibkeys for bibliography entries.

    Default mode fills only entries whose bibkey is NULL or empty.
    Use --all to recompute every entry (normalize existing keys too).
    Use --dry-run to preview changes without writing.
    Use --yes to skip the --all confirmation prompt (required with --json).
    """
    # FIX 1: Guard --all in write mode.
    if recompute_all and not dry_run:
        _guard_recompute_all(as_json=as_json, confirmed=confirmed)

    engine = get_engine_from_ctx(ctx)

    # FIX 2: Backup BEFORE any mutation; abort if backup fails.
    backup: Path | None = None
    if not dry_run:
        try:
            backup = backup_database(engine)
        except OSError as exc:
            raise click.ClickException(
                f"DB backup failed, aborting (no changes made): {exc}"
            )

    with Session(engine) as session:
        changes = compute_recompute_plan(
            session, fill_missing_only=not recompute_all
        )

        if not dry_run:
            apply_recompute(session, changes)
            session.commit()

    if as_json:
        click.echo(format_recompute_json(changes, backup=backup, dry_run=dry_run))
    else:
        if not dry_run and backup is not None:
            click.echo(f"Backup: {backup}")
        click.echo(format_recompute_table(changes, backup=backup, dry_run=dry_run))


# ── keyword subgroup ─────────────────────────────────────────────────────


@prisma.group()
def keyword() -> None:
    """Search keyword management."""


@keyword.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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
@with_schema_guard
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


@review.command(name="stats")
@click.option(
    "--keyword-id",
    required=True,
    type=click.IntRange(min=1),
    help="Keyword ID.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def review_stats(ctx: click.Context, keyword_id: int, as_json: bool) -> None:
    """Per-keyword screening counts."""
    engine = get_engine_from_ctx(ctx)
    try:
        with Session(engine) as session:
            stats = get_review_stats(session, keyword_id)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(format_stats_json(stats))
    else:
        click.echo(format_stats_table(stats))


# ── checklist subgroup ───────────────────────────────────────────────────


@prisma.group()
def checklist() -> None:
    """PRISMA compliance checklist."""


@checklist.command(name="show")
@click.option(
    "--keyword-id",
    type=click.IntRange(min=1),
    default=None,
    help="Scope keyword-specific items to this keyword.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def checklist_show(ctx: click.Context, keyword_id: int | None, as_json: bool) -> None:
    """Show PRISMA compliance checklist from DB state."""
    engine = get_engine_from_ctx(ctx)
    try:
        with Session(engine) as session:
            items = get_checklist(session, keyword_id=keyword_id)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(format_checklist_json(items))
    else:
        click.echo(format_checklist_table(items))
