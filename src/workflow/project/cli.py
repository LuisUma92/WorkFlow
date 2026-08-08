"""``workflow project`` CLI — maturation reporting (ADR ITEP-0009 Part II)."""

from __future__ import annotations

import json as _json
from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db import maturation
from workflow.db.errors import with_schema_guard
from workflow.db.engine import get_engine_from_ctx
from workflow.db.models.knowledge import MainTopic
from workflow.project import service as project_service
from workflow.project.formatters import (
    format_adopt_result_json,
    format_project_list_json,
    format_project_list_table,
)


_TICK = {True: "✓", False: "✗", None: "?"}


@click.group("project")
def project() -> None:
    """Project-level reports and lifecycle helpers."""


@project.command("propose-maturation")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON.",
)
@click.option(
    "--area",
    "area_code",
    default=None,
    help="Only report for the given area DDTTAA code.",
)
@click.pass_context
@with_schema_guard
def propose_maturation(
    ctx: click.Context,
    as_json: bool,
    area_code: str | None,
) -> None:
    """Run :func:`workflow.db.maturation.evaluate_area` over every area."""
    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        query = session.query(MainTopic).filter(MainTopic.parent_id.is_(None))
        if area_code is not None:
            query = query.filter(MainTopic.code == area_code)
        areas = query.order_by(MainTopic.code).all()

        if not areas:
            click.echo("No area-level MainTopic rows found.")
            return

        report: list[dict] = []
        for area in areas:
            signals = maturation.evaluate_area(session, area.id)
            mature = maturation.is_mature(signals)
            report.append(
                {
                    "area_code": area.code,
                    "area_name": area.name,
                    "mature": mature,
                    "signals": [
                        {
                            "criterion": s.criterion,
                            "met": s.met,
                            "evidence": s.evidence,
                        }
                        for s in signals
                    ],
                }
            )

    if as_json:
        click.echo(_json.dumps(report, ensure_ascii=False, indent=2))
        return

    for entry in report:
        click.echo(
            f"\n{entry['area_code']} — {entry['area_name']} "
            f"(mature={entry['mature']})"
        )
        for s in entry["signals"]:
            tick = _TICK[s["met"]]
            click.echo(f"  {tick} {s['criterion']:<30} {s['evidence']}")


@project.command("list")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON.",
)
@click.pass_context
@with_schema_guard
def list_projects(ctx: click.Context, as_json: bool) -> None:
    """List every registered GeneralProject and LectureInstance."""
    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        rows = project_service.list_projects(session)

    if as_json:
        click.echo(format_project_list_json(rows))
        return
    click.echo(format_project_list_table(rows))


@project.command("adopt")
@click.argument("path", type=click.Path())
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Compute what would happen without writing to the DB.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON.",
)
@click.pass_context
@with_schema_guard
def adopt(ctx: click.Context, path: str, dry_run: bool, as_json: bool) -> None:
    """Register an existing repo directory as a GeneralProject.

    PATH must be named DDTTAA-YYPP-title (ADR ITEP-0008). Never creates
    directories, never writes config.yaml, never touches PATH's contents —
    the non-interactive counterpart of `inittex` for historical repos.
    """
    engine = get_engine_from_ctx(ctx)
    target = Path(path).expanduser()
    with Session(engine) as session:
        result = project_service.adopt_project(session, target, dry_run=dry_run)

    if as_json:
        click.echo(format_adopt_result_json(result))
        return

    if result.dry_run:
        click.echo(
            f"[dry-run] Would adopt {result.main_topic_code} "
            f"({result.title}) — no DB write performed."
        )
        return
    if result.created:
        click.echo(
            f"Adopted {result.main_topic_code} ({result.title}) as "
            f"GeneralProject id={result.project_id}."
        )
    else:
        click.echo(
            f"{result.main_topic_code} ({result.title}) was already "
            f"registered as GeneralProject id={result.project_id}."
        )
