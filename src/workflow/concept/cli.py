"""ITEP-0012 — workflow concept CLI group.

Six subcommands: list, show, add, tree, rm, rename.
Delegates to service layer; sessions via get_engine_from_ctx.
Mirrors src/workflow/evaluation/cli.py pattern.
"""

from __future__ import annotations

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.concept.formatters import (
    format_concept_json,
    format_concept_show_json,
    format_concept_show_table,
    format_concepts_list_json,
    format_concepts_list_table,
    format_tree_ascii,
    format_tree_json,
)
from workflow.concept.service import (
    ConceptError,
    ContentNotFound,
    DuplicateCode,
    HasReferences,
    MainTopicNotFound,
    UnknownCode,
    add_concept,
    build_concept_tree,
    get_concept,
    list_concepts,
    remove_concept,
    rename_concept,
)

__all__ = ["concept"]

_get_engine = get_engine_from_ctx


# ── Group ─────────────────────────────────────────────────────────────────


@click.group()
def concept() -> None:
    """Manage Concept entries (GlobalBase)."""


# ── list ──────────────────────────────────────────────────────────────────


@concept.command(name="list")
@click.option(
    "--main-topic",
    "main_topic_code",
    default=None,
    help="Filter to concepts under MainTopic.code (DDTTAA).",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_list(
    ctx: click.Context,
    main_topic_code: str | None,
    as_json: bool,
) -> None:
    """List concept entries."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            concepts = list_concepts(session, main_topic_code=main_topic_code)
        except MainTopicNotFound as exc:
            raise click.ClickException(str(exc))

        if as_json:
            click.echo(format_concepts_list_json(concepts))
        else:
            click.echo(format_concepts_list_table(concepts))


# ── show ──────────────────────────────────────────────────────────────────


@concept.command(name="show")
@click.argument("code")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_show(ctx: click.Context, code: str, as_json: bool) -> None:
    """Show a single concept with child count."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        c = get_concept(session, code)
        if c is None:
            raise click.ClickException(f"Concept {code!r} not found.")

        from workflow.db.models.knowledge import Concept as _Concept

        child_count = session.query(_Concept).filter(_Concept.parent_id == c.id).count()

        if as_json:
            click.echo(format_concept_show_json(c, child_count))
        else:
            click.echo(format_concept_show_table(c, child_count))


# ── add ───────────────────────────────────────────────────────────────────


@concept.command(name="add")
@click.option("--code", "code", required=True, help="Slug code (e.g. newton-2nd).")
@click.option("--label", "label", required=True, help="Display label.")
@click.option(
    "--content-id",
    "content_id",
    required=True,
    type=click.IntRange(min=1),
    help="Numeric FK to Content.id this concept belongs to (must be ≥ 1).",
)
@click.option(
    "--domain",
    "domain",
    required=True,
    help="Taxonomy domain (e.g. 'Información').",
)
@click.option(
    "--parent",
    "parent_code",
    default=None,
    help="Optional parent concept code.",
)
@click.option("--description", default=None, help="Optional description.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_add(
    ctx: click.Context,
    code: str,
    label: str,
    content_id: int,
    domain: str,
    parent_code: str | None,
    description: str | None,
    as_json: bool,
) -> None:
    """Create a new concept."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            c = add_concept(
                session,
                code=code,
                label=label,
                content_id=content_id,
                domain=domain,
                parent_code=parent_code,
                description=description,
            )
            session.commit()
            session.refresh(c)
        except (ConceptError, ContentNotFound, DuplicateCode) as exc:
            raise click.ClickException(str(exc))

        if as_json:
            click.echo(format_concept_json(c))
        else:
            click.echo(f"Created concept: {c.code!r} — {c.label} (id={c.id})")


# ── tree ──────────────────────────────────────────────────────────────────


@concept.command(name="tree")
@click.option(
    "--main-topic",
    "main_topic_code",
    default=None,
    help="Filter to a specific MainTopic.code.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def cmd_tree(
    ctx: click.Context,
    main_topic_code: str | None,
    as_json: bool,
) -> None:
    """Display concept hierarchy as a tree."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            tree = build_concept_tree(session, main_topic_code=main_topic_code)
        except MainTopicNotFound as exc:
            raise click.ClickException(str(exc))

        if as_json:
            click.echo(format_tree_json(tree))
        else:
            if not tree:
                click.echo("No concepts found.")
            else:
                click.echo(format_tree_ascii(tree))


# ── rm ────────────────────────────────────────────────────────────────────


@concept.command(name="rm")
@click.argument("code")
@click.option(
    "--force",
    is_flag=True,
    help="Cascade-delete NoteConcept rows; reparent child concepts to grandparent.",
)
@click.pass_context
@with_schema_guard
def cmd_rm(ctx: click.Context, code: str, force: bool) -> None:
    """Remove a concept."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            remove_concept(session, code, force=force)
            session.commit()
        except UnknownCode as exc:
            raise click.ClickException(str(exc))
        except HasReferences as exc:
            raise click.ClickException(str(exc))

    click.echo(f"Removed concept {code!r}.")


# ── rename ────────────────────────────────────────────────────────────────


@concept.command(name="rename")
@click.argument("old_code")
@click.argument("new_code")
@click.pass_context
@with_schema_guard
def cmd_rename(ctx: click.Context, old_code: str, new_code: str) -> None:
    """Rename a concept (atomic slug change)."""
    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            rename_concept(session, old_code, new_code)
            session.commit()
        except (UnknownCode, DuplicateCode, ConceptError) as exc:
            raise click.ClickException(str(exc))

    click.echo(f"Renamed concept {old_code!r} → {new_code!r}.")
