from __future__ import annotations

import sys
from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.latex.units import (
    default_units_sty_path,
    find_undeclared_units,
    format_unit_warnings,
    load_declared_units,
)
from workflow.validation.parsers import parse_md_frontmatter, parse_tex_metadata
from workflow.validation.schemas import (
    check_concepts_against_db,
    check_discipline_area_consistency,
    check_graph_against_db,
    check_main_topic_against_db,
    validate_exercise_metadata,
    validate_note_frontmatter,
)


def _run_graph_check(session: Session) -> bool:
    """Run graph validation and print results.  Returns True if any errors found."""
    graph_issues = check_graph_against_db(session)
    if not graph_issues:
        click.echo("\nGraph: no issues found.")
        return False
    click.echo("\nGraph issues:")
    has_errors = False
    for issue in graph_issues:
        prefix = "  - " if issue["severity"] == "error" else "  ! "
        click.echo(f"{prefix}[{issue['severity'].upper()}] {issue['message']}")
        if issue["severity"] == "error":
            has_errors = True
    return has_errors


def _validate_note_file(
    filepath: Path,
    session: Session,
    strict_main_topic: bool,
    strict_concepts: bool,
) -> tuple[list[str], list[str]]:
    """Validate a single note file; returns (file_errors, file_warnings)."""
    frontmatter = parse_md_frontmatter(filepath)
    if frontmatter is None:
        click.echo(f"{filepath}: [SKIP] no frontmatter found")
        return [], []

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
            check_discipline_area_consistency(mt_obj, fm.discipline_area, session)
        )
        for issue in check_concepts_against_db(fm, session, strict=strict_concepts):
            if issue["severity"] == "error":
                file_errors.append(issue["message"])
            else:
                file_warnings.append(issue["message"])

    return file_errors, file_warnings


@click.group()
def validate():
    """Validate frontmatter and metadata schemas."""
    pass


@validate.command()
@click.pass_context
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
@click.option(
    "--strict-main-topic",
    is_flag=True,
    default=False,
    help="Treat unknown main_topic slug/id as error (Phase B / ITEP-0009 Part II).",
)
@click.option(
    "--strict-concepts",
    is_flag=True,
    default=False,
    help="Treat unknown concept codes / main_topic mismatches as errors (ITEP-0012).",
)
@click.option(
    "--graph",
    is_flag=True,
    default=False,
    help=(
        "After per-file validation, run a vault-wide NoteEdge graph check for "
        "cycles, unresolved edges, orphan notes, self-edges, and duplicate edges "
        "(ITEP-0013).  This check is global/vault-wide — it is NOT scoped to the "
        "PATH argument."
    ),
)
def notes(
    ctx: click.Context,
    path: str,
    recursive: bool,
    strict_main_topic: bool,
    strict_concepts: bool,
    graph: bool,
) -> None:
    """Validate YAML frontmatter in Markdown notes."""
    root = Path(path)
    files = sorted(root.rglob("*.md") if recursive else root.glob("*.md"))
    total = valid = invalid = warnings = 0

    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        for filepath in files:
            total += 1
            file_errors, file_warnings = _validate_note_file(
                filepath, session, strict_main_topic, strict_concepts
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
        # Graph check runs inside the open session (ITEP-0013 P3).
        graph_has_errors = _run_graph_check(session) if graph else False

    if invalid or graph_has_errors:
        sys.exit(1)


def _lint_unit_warnings(filepath: Path, declared_units: frozenset[str]) -> list[str]:
    """Warn (never error) on `\\si`/`\\SI` unit macros not in builtins ∪ declared."""
    try:
        tex_body = filepath.read_text(encoding="utf-8")
    except OSError:
        return []
    if not tex_body:
        return []
    return format_unit_warnings(find_undeclared_units(tex_body, declared_units))


@validate.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
def exercises(path: str, recursive: bool) -> None:
    """Validate commented YAML metadata in exercise .tex files."""
    root = Path(path)
    files = sorted(root.rglob("*.tex") if recursive else root.glob("*.tex"))
    declared_units = load_declared_units(default_units_sty_path())

    total = 0
    valid = 0
    invalid = 0
    warned = 0

    for filepath in files:
        total += 1
        unit_warnings = _lint_unit_warnings(filepath, declared_units)

        metadata = parse_tex_metadata(filepath)

        if metadata is None:
            click.echo(f"{filepath}: [SKIP] no metadata block found")
            if unit_warnings:
                warned += 1
                click.echo(f"{filepath}:")
                for w in unit_warnings:
                    click.echo(f"  ! {w}")
            continue

        _, errors, warnings = validate_exercise_metadata(metadata)
        warnings = warnings + unit_warnings
        if errors:
            invalid += 1
            click.echo(f"{filepath}:")
            for err in errors:
                click.echo(f"  - {err}")
        else:
            valid += 1
        if warnings:
            warned += 1
            click.echo(f"{filepath}:")
            for w in warnings:
                click.echo(f"  ! {w}")

    click.echo(
        f"\nSummary: {total} files checked, {valid} valid, "
        f"{invalid} with errors, {warned} with warnings."
    )

    if invalid:
        sys.exit(1)
