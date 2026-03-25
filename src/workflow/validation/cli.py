from __future__ import annotations

from pathlib import Path

import click

from workflow.validation.parsers import parse_md_frontmatter, parse_tex_metadata
from workflow.validation.schemas import (
    validate_note_frontmatter,
    validate_exercise_metadata,
)


@click.group()
def validate():
    """Validate frontmatter and metadata schemas."""
    pass


@validate.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
def notes(path: str, recursive: bool) -> None:
    """Validate YAML frontmatter in Markdown notes."""
    root = Path(path)
    pattern = "**/*.md" if recursive else "*.md"
    files = sorted(root.rglob("*.md") if recursive else root.glob("*.md"))

    total = 0
    valid = 0
    invalid = 0

    for filepath in files:
        total += 1
        frontmatter = parse_md_frontmatter(filepath)

        if frontmatter is None:
            click.echo(f"{filepath}: [SKIP] no frontmatter found")
            continue

        _, errors = validate_note_frontmatter(frontmatter)
        if errors:
            invalid += 1
            click.echo(f"{filepath}:")
            for err in errors:
                click.echo(f"  - {err}")
        else:
            valid += 1

    click.echo(f"\nSummary: {total} files checked, {valid} valid, {invalid} with errors.")


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

    click.echo(f"\nSummary: {total} files checked, {valid} valid, {invalid} with errors.")
