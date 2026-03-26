"""Lecture CLI commands — Phase 5.

Click command group wired into the main ``workflow`` CLI.
Provides: scan, split, link, build-eval.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
from sqlalchemy.orm import Session

from workflow.lecture.linker import link_lecture_files
from workflow.lecture.note_splitter import split_notes_file
from workflow.lecture.scanner import register_notes, scan_lecture_directory

_MAX_EXERCISE_POOL = 10_000


def _get_local_engine(project_root: Path) -> Any:
    """Initialise and return a local slipbox.db engine."""
    from workflow.db.engine import init_local_db

    return init_local_db(project_root=project_root)


@click.group()
def lectures() -> None:
    """Lecture project management."""


@lectures.command()
@click.argument("lecture-dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project root containing slipbox.db.",
)
def scan(lecture_dir: str, project_root: str) -> None:
    """Scan lecture directory and register .tex files as notes."""
    lecture_path = Path(lecture_dir).resolve()
    root_path = Path(project_root).resolve()

    engine = _get_local_engine(root_path)

    with Session(engine) as session:
        result = register_notes(lecture_path, session)
        session.commit()

    total = len(result.discovered)
    new = len(result.registered)
    existing = len(result.already_registered)

    click.echo(f"Discovered: {total} .tex file(s)")
    click.echo(f"  Registered (new): {new}")
    click.echo(f"  Already registered: {existing}")

    if result.warnings:
        for w in result.warnings:
            click.echo(f"  [WARN] {w}", err=True)

    for filename in result.registered:
        click.echo(f"  + {filename}")


@lectures.command()
@click.argument("source-file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(file_okay=False),
    default=None,
    help="Directory to write split files into (default: source file's directory).",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing output files.",
)
def split(source_file: str, output_dir: str | None, overwrite: bool) -> None:
    """Split a notes file at %>path markers into separate files."""
    src = Path(source_file).resolve()
    out = Path(output_dir).resolve() if output_dir else src.parent

    result = split_notes_file(src, out, overwrite=overwrite)

    total = len(result.files)
    created = sum(1 for f in result.files if f.created)
    skipped = total - created

    click.echo(f"Source: {src}")
    click.echo(f"Split files: {total}")
    click.echo(f"  Created: {created}")
    click.echo(f"  Skipped (already exist): {skipped}")

    for sf in result.files:
        status = "created" if sf.created else "skipped"
        click.echo(f"  [{status}] {sf.output_path}  ({sf.line_count} lines)")

    if result.warnings:
        for w in result.warnings:
            click.echo(f"  [WARN] {w}", err=True)

    if not result.files:
        click.echo("No markers found — nothing to split.")


@lectures.command()
@click.argument("lecture-dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Project root containing slipbox.db.",
)
def link(lecture_dir: str, project_root: str) -> None:
    """Scan lecture files for references and update link tables."""
    lecture_path = Path(lecture_dir).resolve()
    root_path = Path(project_root).resolve()

    engine = _get_local_engine(root_path)

    with Session(engine) as session:
        tex_files = scan_lecture_directory(lecture_path)
        result = link_lecture_files(tex_files, session)
        session.commit()

    click.echo(f"References found:   {result.references_found}")
    click.echo(f"Citations found:    {result.citations_found}")
    click.echo(f"Citations created:  {result.citations_created}")
    click.echo(f"Links created:      {result.links_created}")

    if result.warnings:
        for w in result.warnings:
            click.echo(f"  [WARN] {w}", err=True)


@lectures.command(name="build-eval")
@click.option("--taxonomy-level", "-l", multiple=True, required=True,
              help="Taxonomy level(s) to select exercises for.")
@click.option("--taxonomy-domain", "-d", multiple=True,
              help="Taxonomy domain(s) (parallel to --taxonomy-level).")
@click.option("--count", "-n", type=int, default=5, show_default=True,
              help="Number of exercises to select per slot.")
@click.option("--points", "-p", type=float, default=10.0, show_default=True,
              help="Points per exercise.")
@click.option("--title", type=str, default="Evaluación", show_default=True,
              help="Evaluation title.")
@click.option("--output", "-o", type=click.Path(),
              help="Output .tex file path.")
@click.option("--moodle", is_flag=True,
              help="Also export Moodle XML alongside the output file.")
@click.pass_context
def build_eval(
    ctx: click.Context,
    taxonomy_level: tuple,
    taxonomy_domain: tuple,
    count: int,
    points: float,
    title: str,
    output: str | None,
    moodle: bool,
) -> None:
    """Build evaluation from exercise bank.

    Selects exercises matching taxonomy criteria, assembles exam document,
    and optionally exports to Moodle XML.
    """
    from workflow.db.engine import init_global_db
    from workflow.db.repos.sqlalchemy import SqlExerciseRepo
    from workflow.exercise.selector import select_exercises
    from workflow.exercise.exam_builder import build_exam
    from workflow.lecture.eval_builder import build_eval_spec

    # Build items list pairing each level with corresponding domain (or "")
    items = []
    for i, level in enumerate(taxonomy_level):
        domain = taxonomy_domain[i] if i < len(taxonomy_domain) else ""
        items.append({
            "taxonomy_level": level,
            "taxonomy_domain": domain,
            "total_amount": count,
            "points_per_item": points,
        })

    spec = build_eval_spec(title, items)

    # Query DB for complete exercises
    engine = init_global_db()
    with Session(engine) as session:
        repo = SqlExerciseRepo(session)
        pool = repo.find_by_filters(status="complete", limit=_MAX_EXERCISE_POOL)

        selection = select_exercises(list(spec.slots), pool)
        exam = build_exam(selection, title=title)

        click.echo(f"Title: {exam.title}")
        click.echo(f"Exercises selected: {exam.exercise_count}")
        click.echo(f"Total points: {exam.total_points:g}")

        if exam.warnings:
            for w in exam.warnings:
                click.echo(f"  [WARN] {w}", err=True)

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(exam.content, encoding="utf-8")
            click.echo(f"Written: {out_path}")

            if moodle:
                from workflow.exercise.moodle import exercises_to_quiz_xml
                from workflow.exercise.parser import parse_exercise
                xml_path = out_path.with_suffix(".xml")
                parsed = []
                for slot_exercises in selection.selected.values():
                    for ex in slot_exercises:
                        text = Path(ex.source_path).read_text(encoding="utf-8")
                        pr = parse_exercise(text)
                        if pr.exercise:
                            parsed.append(pr.exercise)
                xml_content = exercises_to_quiz_xml(parsed)
                xml_path.write_text(xml_content, encoding="utf-8")
                click.echo(f"Moodle XML: {xml_path}")
