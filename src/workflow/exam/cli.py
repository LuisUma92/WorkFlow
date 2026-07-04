"""Exam CLI commands.

Click command group ``exam`` wired into the main ``workflow`` CLI.
Currently provides a single subcommand: ``scaffold-xml``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import click

from workflow.exam.scaffold import parse_blocks_spec, build_moodle_quiz_xml
from workflow.exam.validate import validate_moodle_xml
from workflow.exam.weekly import (
    build_weekly_quiz_xml,
    count_weekly_questions,
    parse_dc_headings,
    tema_label_for_practica,
)

__all__ = ["exam"]


@click.group("exam")
def exam() -> None:
    """Exam authoring utilities (scaffold, export)."""


_LEGACY_OPTION_NAMES = ("--cycle", "--group", "--label", "--category", "--blocks")
_WEEKLY_OPTION_NAMES = ("--week", "--dc", "--kind")


def _detect_scaffold_mode(
    *, cycle, group, label, category, blocks, week, dc, kind,
) -> str:
    """Detect legacy vs weekly scaffold-xml mode from the raw option values.

    Returns ``"legacy"`` or ``"weekly"``. Raises ``click.UsageError`` (exit
    code 2) if required options for the detected mode are missing, or if
    options from both modes are supplied together.
    """
    legacy_values = (cycle, group, label, category, blocks)
    weekly_values = (week, dc, kind)
    legacy_set = any(v is not None for v in legacy_values)
    weekly_set = any(v is not None for v in weekly_values)

    if legacy_set and weekly_set:
        raise click.UsageError(
            "Cannot mix legacy options ({}) with weekly options ({}) — "
            "pick one mode.".format(
                ", ".join(_LEGACY_OPTION_NAMES), ", ".join(_WEEKLY_OPTION_NAMES)
            )
        )

    if weekly_set:
        missing = [
            name for name, value in zip(_WEEKLY_OPTION_NAMES, weekly_values)
            if value is None
        ]
        if missing:
            raise click.UsageError(
                f"Weekly mode requires: {', '.join(missing)}"
            )
        return "weekly"

    missing = [
        name for name, value in zip(_LEGACY_OPTION_NAMES, legacy_values)
        if value is None
    ]
    if missing:
        raise click.UsageError(
            f"Legacy mode requires: {', '.join(missing)}"
        )
    return "legacy"


def _write_xml(out: str, xml_text: str) -> Path:
    """Write the scaffold XML to disk, exit 1 on unwritable path."""
    out_path = Path(out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml_text, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Cannot write to {out!r}: {exc}") from exc
    return out_path


def _run_legacy_scaffold(
    *, course, cycle, group, label, category, blocks,
    question_prefix, penalty, grade, out, as_json,
) -> None:
    """Legacy ``--blocks``-driven scaffold-xml mode (unchanged behavior)."""
    try:
        blocks_parsed = parse_blocks_spec(blocks)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    xml_text = build_moodle_quiz_xml(
        course=course,
        cycle=cycle,
        group=group,
        label=label,
        category=category,
        blocks=blocks_parsed,
        question_prefix=question_prefix,
        penalty=penalty,
        grade=grade,
    )

    out_path = _write_xml(out, xml_text)

    valid_xml = True
    try:
        body = xml_text.split("\n", 1)[1] if xml_text.startswith("<?xml") else xml_text
        ET.fromstring(body)
    except ET.ParseError:
        valid_xml = False

    total_questions = sum(c for _, c in blocks_parsed) + 1  # +1 for category question
    multichoice_count = total_questions - 1

    if as_json:
        click.echo(
            json.dumps(
                {
                    "path": str(out_path),
                    "questions": total_questions,
                    "blocks": [{"name": n, "count": c} for n, c in blocks_parsed],
                    "valid_xml": valid_xml,
                }
            )
        )
    else:
        click.echo(
            f"Wrote {total_questions} questions "
            f"(1 category + {multichoice_count} multichoice) to {out}"
        )


def _run_weekly_scaffold(
    *, course, week, dc, kind, category_style, out, as_json,
) -> None:
    """Weekly DC.md-driven scaffold-xml mode."""
    try:
        categories = parse_dc_headings(dc)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        xml_text = build_weekly_quiz_xml(
            course=course,
            week=week,
            kind=kind,
            categories=categories,
            category_style=category_style,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    out_path = _write_xml(out, xml_text)
    total_questions = count_weekly_questions(categories)

    tema_label = tema_label_for_practica(week) if kind == "practica" else None

    if as_json:
        click.echo(
            json.dumps(
                {
                    "path": str(out_path),
                    "course": course,
                    "week": week,
                    "kind": kind,
                    "category_style": category_style,
                    "categories": categories,
                    "questions": total_questions,
                    "tema_label": tema_label,
                }
            )
        )
    else:
        click.echo(
            f"Wrote {total_questions} questions "
            f"({len(categories)} category + {len(categories)} multichoice stub) to {out}"
        )


@exam.command("scaffold-xml")
@click.option("--course", required=True, help="Course code, e.g. FS0211")
@click.option("--cycle", default=None, help="[legacy mode] Academic cycle, e.g. 2026C1")
@click.option("--group", default=None, help="[legacy mode] Group identifier, e.g. 001")
@click.option("--label", default=None, help="[legacy mode] Exam label, e.g. PC04")
@click.option("--category", default=None, help="[legacy mode] Moodle category path")
@click.option(
    "--blocks",
    default=None,
    help="[legacy mode] Comma-separated Name:count pairs, e.g. 'Recordar:4,Comprender:4'",
)
@click.option("--question-prefix", default="", show_default=True, help="[legacy mode] Optional prefix for question names")
@click.option("--penalty", default=0.25, show_default=True, type=float, help="[legacy mode] Per-wrong-answer penalty")
@click.option("--grade", default=1, show_default=True, type=int, help="[legacy mode] Default grade per question")
@click.option("--week", default=None, type=int, help="[weekly mode] Week number, e.g. 11")
@click.option("--dc", default=None, type=click.Path(exists=True, dir_okay=False), help="[weekly mode] Path to DC.md")
@click.option("--kind", default=None, type=click.Choice(["comprension", "practica"]), help="[weekly mode] Quiz kind")
@click.option(
    "--category-style",
    default="flat",
    show_default=True,
    type=click.Choice(["flat", "hierarchical"]),
    help="[weekly mode] Moodle category packaging style",
)
@click.option("--out", "-o", required=True, help="Output XML file path")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON summary instead of prose")
def cmd_scaffold_xml(
    course: str,
    cycle,
    group,
    label,
    category,
    blocks,
    question_prefix: str,
    penalty: float,
    grade: int,
    week,
    dc,
    kind,
    category_style: str,
    out: str,
    as_json: bool,
) -> None:
    """Generate a Moodle XML quiz skeleton with CDATA[TODO] placeholders.

    Two mutually-exclusive modes, detected from which options are supplied:

    \b
    - legacy mode: --cycle --group --label --category --blocks (all required together)
    - weekly mode: --week --dc --kind (all required together)
    """
    mode = _detect_scaffold_mode(
        cycle=cycle, group=group, label=label, category=category, blocks=blocks,
        week=week, dc=dc, kind=kind,
    )

    if mode == "weekly":
        _run_weekly_scaffold(
            course=course, week=week, dc=dc, kind=kind,
            category_style=category_style, out=out, as_json=as_json,
        )
    else:
        _run_legacy_scaffold(
            course=course, cycle=cycle, group=group, label=label, category=category,
            blocks=blocks, question_prefix=question_prefix, penalty=penalty,
            grade=grade, out=out, as_json=as_json,
        )


def _echo_json_report(report) -> None:
    """Emit the JSON report shape for ``exam validate --json``."""
    click.echo(
        json.dumps(
            {
                "file": report.file,
                "questions": report.questions,
                "violations": [
                    {"question": v.question, "rule": v.rule, "detail": v.detail}
                    for v in report.violations
                ],
            }
        )
    )


def _echo_human_report(report) -> None:
    """Emit the human-readable report for ``exam validate``."""
    for v in report.violations:
        click.echo(f"{v.question}: {v.rule} — {v.detail}")
    click.echo(f"{'OK' if not report.violations else 'FAIL'}: "
               f"{report.questions} questions, {len(report.violations)} violations")


@exam.command("validate")
@click.argument("xml_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--strict", is_flag=True, default=False, help="Also enforce idnumber + category rules")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON report instead of prose")
def cmd_validate(xml_file: str, strict: bool, as_json: bool) -> None:
    """Lint a Moodle XML quiz export for structural issues."""
    try:
        report = validate_moodle_xml(xml_file, strict=strict)
    except ValueError as exc:
        raise click.ClickException(f"XML parse error: {exc}") from exc

    if as_json:
        _echo_json_report(report)
    else:
        _echo_human_report(report)

    if report.violations:
        sys.exit(1)
