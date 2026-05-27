"""Evaluation and taxonomy item CLI commands.

Click command groups wired into the main ``workflow`` CLI.
Groups: ``evaluations`` and ``item``.
"""

from __future__ import annotations

import click

from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.db.repos.sqlalchemy import (
    SqlCourseRepo,
    SqlEvalTemplateRepo,
    SqlItemRepo,
)
from workflow.db.models.academic import _TAXONOMY_DOMAINS, _TAXONOMY_LEVELS
from workflow.evaluation.formatters import (
    format_course_json,
    format_course_table,
    format_eval_detail_json,
    format_eval_detail_table,
    format_eval_json,
    format_eval_table,
    format_item_json,
    format_item_table,
    format_practice_json,
    format_practice_single_json,
    format_practice_table,
)
from workflow.evaluation.service import (
    add_evaluation_item,
    add_practice,
    create_course,
    create_evaluation_template,
    create_item,
    list_practices,
    remove_evaluation_item,
    rename_evaluation_template,
)

__all__ = ["evaluations", "item", "course"]


_get_engine = get_engine_from_ctx


# ── evaluations group ─────────────────────────────────────────────────────


@click.group()
def evaluations() -> None:
    """Evaluation template management."""


@evaluations.command(name="list")
@click.option("--inst", default=None, help="Filter by institution short name.")
@click.option("--full", is_flag=True, help="Show item breakdown per template.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def eval_list(ctx: click.Context, inst: str | None, full: bool, as_json: bool) -> None:
    """List evaluation templates."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlEvalTemplateRepo(session)
        templates = repo.list_all(institution=inst)

        if as_json:
            click.echo(format_eval_json(templates, full=full))
        else:
            click.echo(format_eval_table(templates, full=full))


@evaluations.command(name="show")
@click.argument("template_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def eval_show(ctx: click.Context, template_id: int, as_json: bool) -> None:
    """Show a single evaluation template with item breakdown."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlEvalTemplateRepo(session)
        tmpl = repo.get_detail(template_id)

        if tmpl is None:
            raise click.ClickException(f"Template with id={template_id} not found.")

        if as_json:
            click.echo(format_eval_detail_json(tmpl))
        else:
            click.echo(format_eval_detail_table(tmpl))


@evaluations.command(name="add")
@click.option("--inst", required=True, help="Institution short name.")
@click.option("--name", required=True, help="Template name.")
@click.option("--description", default="", help="Template description.")
@click.pass_context
@with_schema_guard
def eval_add(ctx: click.Context, inst: str, name: str, description: str) -> None:
    """Create a new evaluation template."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        try:
            tmpl = create_evaluation_template(
                session,
                institution_short_name=inst,
                name=name,
                description=description,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(f"Created template: [{inst}] {tmpl.name} (id={tmpl.id})")


@evaluations.group(name="edit")
@click.argument("template_id", type=int)
@click.pass_context
@with_schema_guard
def eval_edit(ctx: click.Context, template_id: int) -> None:
    """Edit an evaluation template (rename, add/remove items)."""
    ctx.ensure_object(dict)["template_id"] = template_id


@eval_edit.command(name="rename")
@click.option("--name", required=True, help="New template name.")
@click.pass_context
@with_schema_guard
def eval_rename(ctx: click.Context, name: str) -> None:
    """Rename an evaluation template."""
    engine = _get_engine(ctx)
    template_id = ctx.obj["template_id"]

    with Session(engine) as session:
        try:
            tmpl = rename_evaluation_template(
                session,
                template_id=template_id,
                new_name=name,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(f"Renamed template id={tmpl.id} to '{tmpl.name}'")


@eval_edit.command(name="add-item")
@click.option("--item-id", required=True, type=int, help="Item ID to add.")
@click.option("--amount", required=True, type=int, help="Number of items.")
@click.option("--points", required=True, type=int, help="Points per item.")
@click.pass_context
@with_schema_guard
def eval_add_item(ctx: click.Context, item_id: int, amount: int, points: int) -> None:
    """Add a taxonomy item to the template."""
    engine = _get_engine(ctx)
    template_id = ctx.obj["template_id"]

    with Session(engine) as session:
        try:
            ei = add_evaluation_item(
                session,
                template_id=template_id,
                item_id=item_id,
                amount=amount,
                points_per_item=points,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(
            f"Added item id={ei.item_id} to template id={template_id} "
            f"({ei.total_amount} × {ei.points_per_item} pts, id={ei.id})"
        )


@eval_edit.command(name="remove-item")
@click.option(
    "--eval-item-id", required=True, type=int, help="EvaluationItem ID to remove."
)
@click.pass_context
@with_schema_guard
def eval_remove_item(ctx: click.Context, eval_item_id: int) -> None:
    """Remove an item link from the template."""
    engine = _get_engine(ctx)

    template_id = ctx.obj["template_id"]

    with Session(engine) as session:
        try:
            removed = remove_evaluation_item(
                session,
                evaluation_item_id=eval_item_id,
                template_id=template_id,
            )
        except ValueError as e:
            raise click.ClickException(str(e))
        if not removed:
            raise click.ClickException(f"EvaluationItem id={eval_item_id} not found.")
        session.commit()

    click.echo(f"Removed evaluation item id={eval_item_id}")


# ── item group ────────────────────────────────────────────────────────────


@click.group()
def item() -> None:
    """Taxonomy item management."""


@item.command(name="list")
@click.option("--domain", default=None, help="Filter by taxonomy domain.")
@click.option("--level", default=None, help="Filter by taxonomy level.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
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


@item.command(name="taxonomy")
@click.option(
    "--levels",
    "kind",
    flag_value="levels",
    default="levels",
    help="List Bloom taxonomy levels (default).",
)
@click.option(
    "--domains",
    "kind",
    flag_value="domains",
    help="List Bloom taxonomy domains.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@with_schema_guard
def item_taxonomy(kind: str, as_json: bool) -> None:
    """List Bloom taxonomy levels or domains (ADR ITEP-0006)."""
    import json as _json

    values = list(_TAXONOMY_LEVELS) if kind == "levels" else list(_TAXONOMY_DOMAINS)
    if as_json:
        click.echo(
            _json.dumps({"kind": kind, "values": values}, ensure_ascii=False, indent=2)
        )
        return
    header = "Bloom Levels" if kind == "levels" else "Bloom Domains"
    click.echo(header)
    click.echo("-" * len(header))
    for v in values:
        click.echo(v)


@item.command(name="add")
@click.option("--name", required=True, help="Item name.")
@click.option(
    "--level",
    required=True,
    type=click.Choice(list(_TAXONOMY_LEVELS), case_sensitive=False),
    help="Taxonomy level.",
)
@click.option(
    "--domain",
    required=True,
    type=click.Choice(list(_TAXONOMY_DOMAINS), case_sensitive=False),
    help="Taxonomy domain.",
)
@click.option(
    "--item-type",
    type=click.Choice(["SU", "RC", "Desarrollo"], case_sensitive=False),
    default=None,
    help="Item type.",
)
@click.pass_context
@with_schema_guard
def item_add(
    ctx: click.Context,
    name: str,
    level: str,
    domain: str,
    item_type: str | None,
) -> None:
    """Create a new taxonomy item."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        try:
            it = create_item(
                session,
                name=name,
                taxonomy_level=level,
                taxonomy_domain=domain,
                item_type=item_type,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(
            f"Created item: {it.name} "
            f"({it.taxonomy_domain}/{it.taxonomy_level}, id={it.id})"
        )


# ── course group ──────────────────────────────────────────────────────────


@click.group()
def course() -> None:
    """Course management."""


@course.command(name="list")
@click.option("--inst", default=None, help="Filter by institution short name.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
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


@course.command(name="add-practice")
@click.argument("course_code")
@click.option("--name", required=True, help="Practice/quiz title.")
@click.option("--week", required=True, type=int, help="Evaluation week number.")
@click.option(
    "--type",
    "practice_type",
    required=True,
    type=click.Choice(["practice", "quiz"], case_sensitive=False),
    help="Assessment type.",
)
@click.option("--serial", type=int, default=None, help="Serial number (auto-assigned if omitted).")
@click.option("--file", "source_file", default=None, help="Path to source .xml/.tex file.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def course_add_practice(
    ctx: click.Context,
    course_code: str,
    name: str,
    week: int,
    practice_type: str,
    serial: int | None,
    source_file: str | None,
    as_json: bool,
) -> None:
    """Register a lab practice or quiz to a course."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        try:
            ce = add_practice(
                session,
                course_code=course_code,
                name=name,
                week=week,
                practice_type=practice_type,
                serial=serial,
                source_file=source_file,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        if as_json:
            click.echo(format_practice_single_json(ce, course_code))
        else:
            click.echo(
                f"Registered {practice_type} #{ce.serial_number} for {course_code} "
                f"— {name} (week {week}, id={ce.id})"
            )


@course.command(name="practices")
@click.argument("course_code")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.pass_context
@with_schema_guard
def course_practices(ctx: click.Context, course_code: str, as_json: bool) -> None:
    """List registered practices/quizzes for a course."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        try:
            rows = list_practices(session, course_code=course_code)
        except ValueError as e:
            raise click.ClickException(str(e))

        if as_json:
            click.echo(format_practice_json(rows, course_code))
        else:
            click.echo(format_practice_table(rows, course_code))


@course.command(name="add")
@click.option("--inst", required=True, help="Institution short name.")
@click.option("--code", required=True, help="Course code.")
@click.option("--name", required=True, help="Course name.")
@click.option(
    "--lectures-per-week",
    "--lpw",
    type=int,
    default=3,
    show_default=True,
    help="Lectures per week.",
)
@click.option(
    "--hours-per-lecture",
    "--hpl",
    type=int,
    default=2,
    show_default=True,
    help="Hours per lecture.",
)
@click.pass_context
@with_schema_guard
def course_add(
    ctx: click.Context,
    inst: str,
    code: str,
    name: str,
    lectures_per_week: int,
    hours_per_lecture: int,
) -> None:
    """Create a new course."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        try:
            c = create_course(
                session,
                institution_short_name=inst,
                code=code,
                name=name,
                lectures_per_week=lectures_per_week,
                hours_per_lecture=hours_per_lecture,
            )
            session.commit()
        except ValueError as e:
            raise click.ClickException(str(e))

        click.echo(f"Created course: [{inst}] {c.code} — {c.name} (id={c.id})")
