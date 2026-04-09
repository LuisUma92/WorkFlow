"""Evaluation and taxonomy item CLI commands.

Click command groups wired into the main ``workflow`` CLI.
Groups: ``evaluations`` and ``item``.
"""

from __future__ import annotations

from typing import Any

import click
from sqlalchemy.orm import Session

from workflow.db.repos.sqlalchemy import (
    SqlCourseRepo,
    SqlEvalTemplateRepo,
    SqlItemRepo,
)
from workflow.evaluation.formatters import (
    format_course_json,
    format_course_table,
    format_eval_json,
    format_eval_table,
    format_item_json,
    format_item_table,
)

__all__ = ["evaluations", "item", "course"]


def _get_engine(ctx: click.Context) -> Any:
    """Get DB engine from Click context or create default."""
    obj = ctx.ensure_object(dict)
    if "engine" in obj:
        return obj["engine"]
    from workflow.db.engine import init_global_db

    engine = init_global_db()
    obj["engine"] = engine
    return engine


# ── evaluations group ─────────────────────────────────────────────────────


@click.group()
def evaluations() -> None:
    """Evaluation template management."""


@evaluations.command(name="list")
@click.option("--inst", default=None, help="Filter by institution short name.")
@click.option("--full", is_flag=True, help="Show item breakdown per template.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def eval_list(ctx: click.Context, inst: str | None, full: bool, as_json: bool) -> None:
    """List evaluation templates."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlEvalTemplateRepo(session)
        if full:
            # Fetch with eager loading for item details
            ids = [t.id for t in repo.list_all(institution=inst)]
            templates = [
                repo.get_detail(tid) for tid in ids if repo.get_detail(tid) is not None
            ]
        else:
            templates = repo.list_all(institution=inst)

        if as_json:
            click.echo(format_eval_json(templates, full=full))
        else:
            click.echo(format_eval_table(templates, full=full))


# ── item group ────────────────────────────────────────────────────────────


@click.group()
def item() -> None:
    """Taxonomy item management."""


@item.command(name="list")
@click.option("--domain", default=None, help="Filter by taxonomy domain.")
@click.option("--level", default=None, help="Filter by taxonomy level.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def item_list(
    ctx: click.Context,
    domain: str | None,
    level: str | None,
    as_json: bool,
) -> None:
    """List taxonomy items."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlItemRepo(session)
        items = repo.list_all(domain=domain, level=level)

        if as_json:
            click.echo(format_item_json(items))
        else:
            click.echo(format_item_table(items))


# ── course group ──────────────────────────────────────────────────────────


@click.group()
def course() -> None:
    """Course management."""


@course.command(name="list")
@click.option("--inst", default=None, help="Filter by institution short name.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
def course_list(ctx: click.Context, inst: str | None, as_json: bool) -> None:
    """List registered courses."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlCourseRepo(session)
        courses = repo.list_all(institution=inst)

        if as_json:
            click.echo(format_course_json(courses))
        else:
            click.echo(format_course_table(courses))
