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

__all__ = ["exam"]


@click.group("exam")
def exam() -> None:
    """Exam authoring utilities (scaffold, export)."""


@exam.command("scaffold-xml")
@click.option("--course", required=True, help="Course code, e.g. FS0211")
@click.option("--cycle", required=True, help="Academic cycle, e.g. 2026C1")
@click.option("--group", required=True, help="Group identifier, e.g. 001")
@click.option("--label", required=True, help="Exam label, e.g. PC04")
@click.option("--category", required=True, help="Moodle category path")
@click.option(
    "--blocks",
    required=True,
    help="Comma-separated Name:count pairs, e.g. 'Recordar:4,Comprender:4'",
)
@click.option("--question-prefix", default="", show_default=True, help="Optional prefix for question names")
@click.option("--penalty", default=0.25, show_default=True, type=float, help="Per-wrong-answer penalty")
@click.option("--grade", default=1, show_default=True, type=int, help="Default grade per question")
@click.option("--out", required=True, help="Output XML file path")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON summary instead of prose")
def cmd_scaffold_xml(
    course: str,
    cycle: str,
    group: str,
    label: str,
    category: str,
    blocks: str,
    question_prefix: str,
    penalty: float,
    grade: int,
    out: str,
    as_json: bool,
) -> None:
    """Generate a Moodle XML quiz skeleton with CDATA[TODO] placeholders."""
    # Parse blocks spec — exit 1 on invalid input
    try:
        blocks_parsed = parse_blocks_spec(blocks)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # Build XML
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

    # Write output file — exit 1 on unwritable path
    out_path = Path(out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(xml_text, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Cannot write to {out!r}: {exc}") from exc

    # Validate XML by parsing (xmllint not required at runtime)
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
