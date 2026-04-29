"""``workflow project`` CLI — maturation reporting (ADR ITEP-0009 Part II)."""

from __future__ import annotations

import json as _json

import click
from sqlalchemy.orm import Session

from workflow.db import maturation
from workflow.db.engine import get_engine_from_ctx
from workflow.db.models.academic import MainTopic


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
