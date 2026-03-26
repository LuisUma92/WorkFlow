"""Exercise CLI commands — parse, list, sync, gc.

Click command group wired into the main ``workflow`` CLI.
Uses the exercise parser and ExerciseRepo for DB operations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import click
from sqlalchemy.orm import Session

from workflow.db.models.exercises import Exercise, ExerciseOption
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.domain import ParsedExercise
from workflow.exercise.exam_builder import build_exam
from workflow.exercise.generator import generate_exercise_file, generate_from_content
from workflow.exercise.moodle import exercises_to_quiz_xml
from workflow.exercise.parser import parse_exercise
from workflow.exercise.selector import ExerciseSlot, select_exercises

_MAX_FILES = 10_000
_MAX_FILE_BYTES = 10 * 1024 * 1024


def _get_engine(ctx: click.Context) -> Any:
    """Get DB engine from Click context or create default."""
    obj = ctx.ensure_object(dict)
    if "engine" in obj:
        return obj["engine"]
    from workflow.db.engine import init_global_db

    engine = init_global_db()
    obj["engine"] = engine
    return engine


def _file_hash(path: Path) -> str:
    """SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_tex_files(path: Path) -> list[Path]:
    """Find all .tex files in path (file or directory)."""
    if path.is_file():
        return [path] if path.suffix == ".tex" else []
    files = sorted(path.rglob("*.tex"))
    if len(files) > _MAX_FILES:
        raise click.ClickException(
            f"Too many .tex files ({len(files)}); limit is {_MAX_FILES}."
        )
    return files


@click.group()
def exercise() -> None:
    """Exercise bank management."""


@exercise.command()
@click.argument("path", type=click.Path(exists=True))
def parse(path: str) -> None:
    """Parse exercise .tex file(s) and show results."""
    target = Path(path)
    files = _find_tex_files(target)

    if not files:
        click.echo("No .tex files found.")
        return

    error_count = 0
    for filepath in files:
        if filepath.stat().st_size > _MAX_FILE_BYTES:
            click.echo(f"  [SKIP] {filepath.name}: file too large")
            continue

        text = filepath.read_text(encoding="utf-8")
        result = parse_exercise(text, source_path=str(filepath))

        if result.errors:
            click.echo(f"  [ERROR] {filepath.name}")
            for err in result.errors:
                click.echo(f"          {err}")
            error_count += 1
            continue

        ex = result.exercise
        meta_id = ex.metadata.id if ex.metadata else "(no id)"
        click.echo(f"  [OK] {filepath.name}: {meta_id}")
        click.echo(f"       status: {ex.status}, options: {len(ex.options)}")

        if ex.metadata:
            click.echo(
                f"       type: {ex.metadata.type}, difficulty: {ex.metadata.difficulty}"
            )
        if ex.image_refs:
            click.echo(f"       images: {', '.join(ex.image_refs)}")

        for w in result.warnings:
            click.echo(f"       [WARN] {w}")

    if error_count > 0:
        raise click.ClickException(f"{error_count} file(s) had parse errors.")


@exercise.command(name="list")
@click.option(
    "--status",
    type=click.Choice(["placeholder", "in_progress", "complete"], case_sensitive=False),
    default=None,
    help="Filter by status.",
)
@click.option("--difficulty", type=str, default=None, help="Filter by difficulty.")
@click.option(
    "--taxonomy-level", type=str, default=None, help="Filter by taxonomy level."
)
@click.option("--type", "exercise_type", type=str, default=None, help="Filter by type.")
@click.option("--limit", type=int, default=100, show_default=True)
@click.pass_context
def list_exercises(
    ctx, status, difficulty, taxonomy_level, exercise_type, limit
) -> None:
    """List exercises in the database."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlExerciseRepo(session)
        exercises = repo.find_by_filters(
            status=status,
            difficulty=difficulty,
            taxonomy_level=taxonomy_level,
            exercise_type=exercise_type,
            limit=limit,
        )

        if not exercises:
            click.echo("No exercises found.")
            return

        for ex in exercises:
            status_str = ex.status or "?"
            type_str = ex.type or "?"
            diff_str = ex.difficulty or "?"
            click.echo(
                f"  {ex.exercise_id:30s}  {status_str:12s}  "
                f"{type_str:12s}  {diff_str:6s}"
            )

        click.echo(f"\nTotal: {len(exercises)} exercise(s).")


@exercise.command()
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def sync(ctx, path: str) -> None:
    """Sync exercise .tex files to the database.

    Scans PATH for .tex files, parses metadata, and upserts into the
    global exercise bank. Reports new, updated, and unchanged counts.
    """
    engine = _get_engine(ctx)
    target = Path(path)
    files = _find_tex_files(target)

    if not files:
        click.echo("No .tex files found.")
        return

    new_count = 0
    updated_count = 0
    unchanged_count = 0
    skipped_count = 0

    with Session(engine) as session:
        repo = SqlExerciseRepo(session)

        for filepath in files:
            if filepath.stat().st_size > _MAX_FILE_BYTES:
                click.echo(f"  [SKIP] {filepath.name}: file too large")
                skipped_count += 1
                continue

            text = filepath.read_text(encoding="utf-8")
            result = parse_exercise(text, source_path=str(filepath))

            if result.errors:
                click.echo(f"  [SKIP] {filepath.name}: {result.errors[0]}")
                skipped_count += 1
                continue

            ex = result.exercise
            if ex.metadata is None:
                click.echo(f"  [SKIP] {filepath.name}: no metadata")
                skipped_count += 1
                continue

            current_hash = _file_hash(filepath)

            # Check if record exists
            existing = repo.get_by_exercise_id(ex.metadata.id)

            if existing is not None and existing.file_hash == current_hash:
                unchanged_count += 1
                continue

            # Build tags/concepts as JSON strings
            tags_json = json.dumps(ex.metadata.tags) if ex.metadata.tags else None
            concepts_json = (
                json.dumps(ex.metadata.concepts) if ex.metadata.concepts else None
            )

            exercise_record = Exercise(
                exercise_id=ex.metadata.id,
                source_path=str(filepath.resolve()),
                file_hash=current_hash,
                status=ex.status,
                type=ex.metadata.type,
                difficulty=ex.metadata.difficulty,
                taxonomy_level=ex.metadata.taxonomy_level,
                taxonomy_domain=ex.metadata.taxonomy_domain,
                tags=tags_json,
                concepts=concepts_json,
                default_grade=ex.default_grade,
                has_images=len(ex.image_refs) > 0,
                image_refs=json.dumps(list(ex.image_refs)) if ex.image_refs else None,
                diagram_id=ex.diagram_id,
                option_count=len(ex.options),
            )

            result_record = repo.upsert(exercise_record)

            # Clear existing options and rebuild from parsed data
            result_record.options.clear()
            for opt in ex.options:
                result_record.options.append(
                    ExerciseOption(
                        label=opt.label,
                        is_correct=opt.is_correct,
                        sort_order=ord(opt.label) - ord("a"),
                    )
                )

            if existing is not None:
                updated_count += 1
                status_label = "updated"
            else:
                new_count += 1
                status_label = "new"

            click.echo(f"  [{status_label}] {ex.metadata.id}: {ex.status}")

        session.commit()

    click.echo(
        f"\nSync complete: {new_count} new, {updated_count} updated, "
        f"{unchanged_count} unchanged, {skipped_count} skipped."
    )


@exercise.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def gc(ctx, yes: bool) -> None:
    """Remove orphaned exercise records (missing .tex files)."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        repo = SqlExerciseRepo(session)
        orphans = repo.get_orphans()

        if not orphans:
            click.echo("No orphaned exercises found.")
            return

        click.echo(f"Found {len(orphans)} orphaned exercise(s):")
        for ex in orphans:
            click.echo(f"  {ex.exercise_id}: {ex.source_path}")

        if not yes:
            click.confirm("Delete these records?", abort=True)

        for ex in orphans:
            repo.delete(ex.exercise_id)

        session.commit()

    click.echo(f"Removed {len(orphans)} orphaned record(s).")


_EXERCISE_TYPES = ["multichoice", "shortanswer", "essay", "numerical", "truefalse"]
_DIFFICULTIES = ["easy", "medium", "hard"]


@exercise.command()
@click.argument("exercise-id")
@click.option("--output-dir", "-d", type=click.Path(), required=True)
@click.option(
    "--type",
    "exercise_type",
    type=click.Choice(_EXERCISE_TYPES, case_sensitive=False),
    default="essay",
    show_default=True,
)
@click.option(
    "--difficulty",
    type=click.Choice(_DIFFICULTIES, case_sensitive=False),
    default="medium",
    show_default=True,
)
@click.option("--taxonomy-level", type=str, default="Usar-Aplicar", show_default=True)
@click.option(
    "--taxonomy-domain", type=str, default="Procedimiento Mental", show_default=True
)
@click.option("--tag", multiple=True, help="Tag (repeatable).")
@click.option("--book", type=str, default=None, help="Book citation key.")
@click.option("--chapter", type=int, default=None, help="Chapter number.")
@click.option("--exercise-num", type=int, default=None, help="Exercise number.")
def create(
    exercise_id: str,
    output_dir: str,
    exercise_type: str,
    difficulty: str,
    taxonomy_level: str,
    taxonomy_domain: str,
    tag: tuple[str, ...],
    book: str | None,
    chapter: int | None,
    exercise_num: int | None,
) -> None:
    """Create a new exercise placeholder .tex file."""
    out = Path(output_dir)
    result = generate_exercise_file(
        out,
        exercise_id,
        exercise_type=exercise_type,
        difficulty=difficulty,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
        tags=list(tag) if tag else None,
        book_cite=book,
        chapter=chapter,
        exercise_num=exercise_num,
    )
    if result.created:
        click.echo(f"Created: {result.file_path}")
    else:
        click.echo(f"Skipped (already exists): {result.file_path}")


@exercise.command(name="create-range")
@click.option("--output-dir", "-d", type=click.Path(), required=True)
@click.option("--book", type=str, required=True, help="Book citation key.")
@click.option("--chapter", type=int, required=True, help="Chapter number.")
@click.option("--first", type=int, required=True, help="First exercise number.")
@click.option(
    "--last", type=int, required=True, help="Last exercise number (inclusive)."
)
@click.option(
    "--type",
    "exercise_type",
    type=click.Choice(_EXERCISE_TYPES, case_sensitive=False),
    default="essay",
    show_default=True,
)
@click.option(
    "--difficulty",
    type=click.Choice(_DIFFICULTIES, case_sensitive=False),
    default="medium",
    show_default=True,
)
@click.option("--taxonomy-level", type=str, default="Usar-Aplicar", show_default=True)
@click.option(
    "--taxonomy-domain", type=str, default="Procedimiento Mental", show_default=True
)
@click.option("--tag", multiple=True, help="Tag (repeatable).")
def create_range(
    output_dir: str,
    book: str,
    chapter: int,
    first: int,
    last: int,
    exercise_type: str,
    difficulty: str,
    taxonomy_level: str,
    taxonomy_domain: str,
    tag: tuple[str, ...],
) -> None:
    """Create placeholder .tex files for a range of book exercises."""
    if first > last:
        raise click.ClickException(f"--first ({first}) must be <= --last ({last}).")

    out = Path(output_dir)
    results = generate_from_content(
        out,
        book,
        chapter=chapter,
        first_exercise=first,
        last_exercise=last,
        tags=list(tag) if tag else None,
        exercise_type=exercise_type,
        difficulty=difficulty,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
    )

    created = [r for r in results if r.created]
    skipped = [r for r in results if not r.created]

    for r in created:
        click.echo(f"  [created] {r.file_path.name}")
    for r in skipped:
        click.echo(f"  [skipped] {r.file_path.name}")

    click.echo(
        f"\nDone: {len(created)} created, {len(skipped)} skipped "
        f"({len(results)} total)."
    )


def _parse_and_filter(
    files: list[Path],
    status: str,
    tag: tuple[str, ...],
) -> tuple[list[ParsedExercise], list[Path], int]:
    """Parse .tex files and filter by status/tags.

    Returns (exercises, source_dirs, skipped_count).
    """
    exercises = []
    source_dirs: list[Path] = []
    skipped = 0

    for filepath in files:
        if filepath.stat().st_size > _MAX_FILE_BYTES:
            skipped += 1
            continue

        text = filepath.read_text(encoding="utf-8")
        result = parse_exercise(text, source_path=str(filepath))

        if result.errors or result.exercise is None:
            skipped += 1
            continue

        ex = result.exercise

        if ex.status != status:
            continue

        if tag and ex.metadata:
            if not any(t in (ex.metadata.tags or []) for t in tag):
                continue
        elif tag and not ex.metadata:
            continue

        exercises.append(ex)
        source_dirs.append(filepath.parent)

    return exercises, source_dirs, skipped


@exercise.command(name="export-moodle")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output XML file path. Defaults to stdout.",
)
@click.option(
    "--status",
    type=click.Choice(["placeholder", "in_progress", "complete"], case_sensitive=False),
    default="complete",
    show_default=True,
    help="Only export exercises with this status.",
)
@click.option("--tag", multiple=True, help="Filter by tag (repeatable).")
@click.pass_context
def export_moodle(
    ctx, path: str, output: str | None, status: str, tag: tuple[str, ...]
) -> None:
    """Export exercises to Moodle XML format.

    Parses .tex files in PATH, normalizes custom macros to standard
    LaTeX, and generates a Moodle-importable XML quiz file.
    """
    target = Path(path)
    files = _find_tex_files(target)

    if not files:
        click.echo("No .tex files found.")
        return

    exercises, source_dirs, skipped = _parse_and_filter(files, status, tag)

    if not exercises:
        click.echo(f"No exercises found matching filters (status={status}).")
        return

    xml_str = exercises_to_quiz_xml(exercises, source_dirs=source_dirs)

    if output:
        out_path = Path(output)
        out_path.write_text(xml_str, encoding="utf-8")
        click.echo(f"Exported {len(exercises)} exercise(s) to {out_path}")
    else:
        click.echo(xml_str)

    if skipped:
        click.echo(f"({skipped} file(s) skipped due to errors or size)", err=True)


@exercise.command(name="build-exam")
@click.option(
    "--taxonomy-level",
    "-l",
    multiple=True,
    required=True,
    help="Taxonomy level (repeatable).",
)
@click.option(
    "--taxonomy-domain",
    "-d",
    multiple=True,
    help="Taxonomy domain (repeatable, paired with --taxonomy-level by position).",
)
@click.option(
    "--count",
    "-n",
    type=int,
    default=5,
    show_default=True,
    help="Exercises per slot.",
)
@click.option(
    "--points",
    "-p",
    type=float,
    default=10.0,
    show_default=True,
    help="Points per exercise.",
)
@click.option("--title", type=str, default="Exam", show_default=True)
@click.option(
    "--instructions",
    type=str,
    default="",
    help="Exam instructions text.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file path. Defaults to stdout.",
)
@click.pass_context
def build_exam_cmd(
    ctx,
    taxonomy_level: tuple[str, ...],
    taxonomy_domain: tuple[str, ...],
    count: int,
    points: float,
    title: str,
    instructions: str,
    output: str | None,
) -> None:
    """Build an exam by selecting exercises from the bank.

    Each --taxonomy-level creates a slot. Pair --taxonomy-domain values
    positionally with levels (missing domains default to empty string).
    """
    engine = _get_engine(ctx)

    # Build slots — pair levels with domains by index
    slots: list[ExerciseSlot] = []
    for i, level in enumerate(taxonomy_level):
        domain = taxonomy_domain[i] if i < len(taxonomy_domain) else ""
        slots.append(
            ExerciseSlot(
                taxonomy_level=level,
                taxonomy_domain=domain,
                count=count,
                points_per_item=points,
            )
        )

    # Query DB for complete exercises, let select_exercises handle matching
    with Session(engine) as session:
        repo = SqlExerciseRepo(session)
        pool = repo.find_by_filters(status="complete", limit=10_000)

        selection = select_exercises(slots, pool)

        doc = build_exam(selection, title=title, instructions=instructions)

    # Report warnings
    for w in doc.warnings:
        click.echo(f"[WARN] {w}", err=True)

    if selection.unfilled:
        click.echo(
            f"[WARN] {len(selection.unfilled)} slot(s) could not be fully filled.",
            err=True,
        )

    click.echo(
        f"% Built: {doc.exercise_count} exercise(s), {doc.total_points:g} total points",
        err=True,
    )

    if output:
        out_path = Path(output)
        out_path.write_text(doc.content, encoding="utf-8")
        click.echo(f"Exam written to {out_path}")
    else:
        click.echo(doc.content)
