from __future__ import annotations

import sys
from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.validation.parsers import parse_md_frontmatter, parse_tex_metadata
from workflow.validation.schemas import (
    check_discipline_area_consistency,
    check_main_topic_against_db,
    validate_exercise_metadata,
    validate_note_frontmatter,
)


@click.group()
def validate():
    """Validate frontmatter and metadata schemas."""
    pass


@validate.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
@click.option(
    "--strict-main-topic",
    is_flag=True,
    default=False,
    help="Treat unknown main_topic slug/id as error (Phase B / ITEP-0009 Part II).",
)
def notes(path: str, recursive: bool, strict_main_topic: bool) -> None:
    """Validate YAML frontmatter in Markdown notes."""
    root = Path(path)
    files = sorted(root.rglob("*.md") if recursive else root.glob("*.md"))

    total = 0
    valid = 0
    invalid = 0
    warnings = 0

    engine = init_global_db()
    with Session(engine) as session:
        for filepath in files:
            total += 1
            frontmatter = parse_md_frontmatter(filepath)

            if frontmatter is None:
                click.echo(f"{filepath}: [SKIP] no frontmatter found")
                continue

            fm, errors = validate_note_frontmatter(frontmatter)
            file_errors = list(errors)
            file_warnings: list[str] = []

            if fm is not None:
                mt_obj, mt_msgs = check_main_topic_against_db(fm.main_topic, session)
                if mt_msgs:
                    if strict_main_topic:
                        file_errors.extend(mt_msgs)
                    else:
                        file_warnings.extend(mt_msgs)

                file_errors.extend(
                    check_discipline_area_consistency(
                        mt_obj, fm.discipline_area, session
                    )
                )

            if file_errors:
                invalid += 1
                click.echo(f"{filepath}:")
                for err in file_errors:
                    click.echo(f"  - {err}")
            else:
                valid += 1
            if file_warnings:
                warnings += 1
                click.echo(f"{filepath}:")
                for w in file_warnings:
                    click.echo(f"  ! {w}")

    click.echo(
        f"\nSummary: {total} files checked, {valid} valid, "
        f"{invalid} with errors, {warnings} with warnings."
    )
    if invalid:
        sys.exit(1)


@validate.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
def exercises(path: str, recursive: bool) -> None:
    """Validate commented YAML metadata in exercise .tex files."""
    root = Path(path)
    files = sorted(root.rglob("*.tex") if recursive else root.glob("*.tex"))

    total = 0
    valid = 0
    invalid = 0

    for filepath in files:
        total += 1
        metadata = parse_tex_metadata(filepath)

        if metadata is None:
            click.echo(f"{filepath}: [SKIP] no metadata block found")
            continue

        _, errors = validate_exercise_metadata(metadata)
        if errors:
            invalid += 1
            click.echo(f"{filepath}:")
            for err in errors:
                click.echo(f"  - {err}")
        else:
            valid += 1

    click.echo(
        f"\nSummary: {total} files checked, {valid} valid, {invalid} with errors."
    )
