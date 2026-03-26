"""Exercise CLI commands — parse, list, sync, gc.

Click command group wired into the main ``workflow`` CLI.
Uses the exercise parser and ExerciseRepo for DB operations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import click
from sqlalchemy.orm import Session

from workflow.db.models.exercises import Exercise, ExerciseOption
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.parser import parse_exercise

_MAX_FILES = 10_000
_MAX_FILE_BYTES = 10 * 1024 * 1024


def _get_engine(ctx: click.Context):
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
@click.option("--status", type=str, default=None, help="Filter by status.")
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
