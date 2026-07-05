"""Exercise CLI commands — parse, list, sync, gc.

Click command group wired into the main ``workflow`` CLI.
Uses the exercise parser and ExerciseRepo for DB operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from workflow.exercise.domain import ExerciseType
from workflow.util import copy_to_clipboard

if TYPE_CHECKING:
    from workflow.db.models.bibliography import BibEntry

import click
from sqlalchemy.orm import Session

from workflow.db.models.exercises import Exercise
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.db.errors import with_schema_guard
from workflow.bibliography.service import get_bib_entry_by_bibkey, BibKeyAmbiguous
from workflow.concept.service import resolve_concepts
from workflow.exercise.chapter import filter_by_chapter
from workflow.exercise.balance import (
    compute_balance,
    coverage_ratio,
    format_human_table,
    to_dict as balance_to_dict,
    write_csv as write_balance_csv,
)
from workflow.exercise.exam_builder import build_exam
from workflow.exercise.generator import generate_exercise_file, generate_from_content
from workflow.exercise.moodle import exercises_to_quiz_xml
from workflow.exercise.parser import parse_exercise
from workflow.exercise.selector import ExerciseSlot, select_exercises
from workflow.exercise.service import (
    _MAX_FILE_BYTES,
    delete_orphans,
    gc_orphans,
    parse_and_filter,
    sync_exercises,
)

__all__ = ["exercise"]

_MAX_FILES = 10_000


def _get_engine(ctx: click.Context) -> Any:
    """Get DB engine from Click context or create default."""
    obj = ctx.ensure_object(dict)
    if "engine" in obj:
        return obj["engine"]
    from workflow.db.engine import init_global_db

    engine = init_global_db()
    obj["engine"] = engine
    return engine


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


def _sync_files(
    engine,
    files: list[Path],
    strict_concepts: bool = False,
    as_json: bool = False,
    dry_run: bool = False,
    status_filter: str | None = None,
) -> None:
    import sys
    import json as _json

    with Session(engine) as session:
        try:
            result, messages = sync_exercises(
                session,
                files,
                strict_concepts=strict_concepts,
                status_filter=status_filter,
                dry_run=dry_run,
            )
        except ValueError as exc:
            # Strict-concepts failure: every dropped code is joined into
            # exc's message (service.py collects across the whole batch).
            lines = str(exc).split("; ")
            if as_json:
                click.echo(
                    _json.dumps(
                        {
                            "synced": 0,
                            "skipped": 0,
                            "errors": lines,
                            "dropped_concepts": [],
                            "invalid_status": 0,
                            "dry_run": dry_run,
                        },
                        indent=2,
                    )
                )
            else:
                for line in lines:
                    click.echo(f"error: {line}", err=True)
            sys.exit(1)

    if as_json:
        report = {
            "synced": result.new + result.updated,
            "skipped": result.skipped,
            "errors": list(result.errors),
            "dropped_concepts": result.dropped_concepts,
            "invalid_status": result.invalid_status,
            "dry_run": dry_run,
        }
        click.echo(_json.dumps(report, indent=2))
        if result.invalid_status:
            sys.exit(1)
        return

    for msg in messages:
        click.echo(msg)

    dry_run_note = " (dry-run, no changes written)" if dry_run else ""
    click.echo(
        f"\nSync complete: {result.new} new, "
        f"{result.updated} updated, "
        f"{result.unchanged} unchanged, "
        f"{result.skipped} skipped.{dry_run_note}"
    )

    if result.invalid_status:
        click.echo(
            f"error: {result.invalid_status} file(s) skipped due to an "
            "invalid explicit status (see [SKIP] lines above).",
            err=True,
        )
        sys.exit(1)


def _test_bib_entry_existence(
    engine,
    bibkey: str | None,
) -> BibEntry | None:
    """Validate that a bibliography entry exists."""

    if bibkey is None:
        return None

    with Session(engine) as session:
        try:
            entry = get_bib_entry_by_bibkey(session, bibkey)
        except BibKeyAmbiguous as exc:
            raise click.ClickException(
                f"Ambiguous bibkey '{bibkey}': multiple bibliography entries match."
            ) from exc

    if entry is None:
        raise click.ClickException(
            f"Bibliography entry not found for bibkey '{bibkey}'."
        )

    return entry


@click.group()
def exercise() -> None:
    """Exercise bank management."""


@exercise.command()
@click.argument("path", type=click.Path(exists=True))
@with_schema_guard
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


def _exercise_to_dict(ex: Any) -> dict[str, Any]:
    """Serialize an Exercise ORM row to a JSON-serialisable dict."""
    import json as _json

    # Extract the first tag that looks like a course code for the 'course' field.
    tags_raw = ex.tags or "[]"
    try:
        tags_list: list[str] = _json.loads(tags_raw)
    except Exception:
        tags_list = []
    course = tags_list[0] if tags_list else None
    return {
        "id": ex.exercise_id,
        "file": ex.source_path,
        "type": ex.type,
        "course": course,
        "status": ex.status,
        "difficulty": ex.difficulty,
        "taxonomy_level": ex.taxonomy_level,
        "taxonomy_domain": ex.taxonomy_domain,
        "tags": tags_list,
    }


def _apply_chapter_filter(
    exercises: list[Exercise], chapter_number: int, session: Session
) -> list[Exercise]:
    """Filter exercises to a book chapter, reporting drops/warnings to stderr.

    Exercises with no resolvable chapter (no book_id, no matching
    BibContent row, or an out-of-range/unparsable numeric suffix) are
    dropped silently from the returned list but counted — reported as a
    single stderr note, not an error (Phase 2b, freeze-window plan).
    """
    result = filter_by_chapter(exercises, chapter_number, session)
    for warning in result.warnings:
        click.echo(f"warning: {warning}", err=True)
    if result.excluded > 0:
        click.echo(
            f"note: {result.excluded} exercise(s) excluded — no resolvable "
            f"chapter {chapter_number} reference.",
            err=True,
        )
    return list(result.matched)


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
@click.option(
    "--course", type=str, default=None, help="Filter by course code (tag match)."
)
@click.option(
    "--concept", "concept_code", type=str, default=None, help="Filter by concept code."
)
@click.option(
    "--chapter",
    "chapter_number",
    type=int,
    default=None,
    help="Filter to exercises whose reference falls in this book chapter.",
)
@click.option("--limit", type=int, default=100, show_default=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON array.")
@click.pass_context
@with_schema_guard
def list_exercises(
    ctx,
    status,
    difficulty,
    taxonomy_level,
    exercise_type,
    course,
    concept_code,
    chapter_number,
    limit,
    as_json,
) -> None:
    """List exercises in the database."""
    import json as _json
    import sys

    engine = _get_engine(ctx)

    # Build tag filter: course maps to a tag value
    tag_filter = [course] if course else None

    with Session(engine) as session:
        concept_ids: list[int] | None = None
        if concept_code is not None:
            found, _issues = resolve_concepts([concept_code], session, strict=True)
            if not found:
                click.echo(
                    f"error: concept code '{concept_code}' not found in database.",
                    err=True,
                )
                sys.exit(2)
            concept_ids = [found[0].id]

        repo = SqlExerciseRepo(session)
        exercises = repo.find_by_filters(
            status=status,
            difficulty=difficulty,
            taxonomy_level=taxonomy_level,
            exercise_type=exercise_type,
            tags=tag_filter,
            concept_ids=concept_ids,
            limit=limit,
        )

        if chapter_number is not None:
            exercises = _apply_chapter_filter(exercises, chapter_number, session)

        if as_json:
            click.echo(
                _json.dumps([_exercise_to_dict(ex) for ex in exercises], indent=2)
            )
            return

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
@click.option(
    "--strict-concepts",
    "strict_concepts",
    is_flag=True,
    default=False,
    help="Treat unresolved concept codes as errors (abort sync, exit 1).",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON report.")
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Parse and report the diff without writing to the DB.",
)
@click.option(
    "--status",
    "status_filter",
    type=click.Choice(["placeholder", "in_progress", "complete"], case_sensitive=False),
    default=None,
    help="Only sync files whose parsed status matches.",
)
@click.pass_context
@with_schema_guard
def sync(
    ctx,
    path: str,
    strict_concepts: bool,
    as_json: bool,
    dry_run: bool,
    status_filter: str | None,
) -> None:
    """Sync exercise .tex files to the database.

    Scans PATH for .tex files, parses metadata, and upserts into the
    global exercise bank. Reports new, updated, and unchanged counts.
    """
    import json as _json

    engine = _get_engine(ctx)
    target = Path(path)
    files = _find_tex_files(target)

    if not files:
        if as_json:
            click.echo(
                _json.dumps(
                    {
                        "synced": 0,
                        "skipped": 0,
                        "errors": [],
                        "dropped_concepts": [],
                        "invalid_status": 0,
                        "dry_run": dry_run,
                    },
                    indent=2,
                )
            )
        else:
            click.echo("No .tex files found.")
        return

    _sync_files(
        engine,
        files,
        strict_concepts=strict_concepts,
        as_json=as_json,
        dry_run=dry_run,
        status_filter=status_filter,
    )


@exercise.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
@with_schema_guard
def gc(ctx, yes: bool) -> None:
    """Remove orphaned exercise records (missing .tex files)."""
    engine = _get_engine(ctx)

    with Session(engine) as session:
        ids, paths = gc_orphans(session)

        if not ids:
            click.echo("No orphaned exercises found.")
            return

        click.echo(f"Found {len(ids)} orphaned exercise(s):")
        for eid, epath in zip(ids, paths):
            click.echo(f"  {eid}: {epath}")

        if not yes:
            click.confirm("Delete these records?", abort=True)

        count = delete_orphans(session, ids)
        session.commit()

    click.echo(f"Removed {count} orphaned record(s).")


_EXERCISE_TYPES = [e.value for e in ExerciseType]
_DIFFICULTIES = ["easy", "medium", "hard"]


@exercise.command()
@click.option("--output-dir", "-d", type=click.Path(), required=True)
@click.option(
    "--type",
    "exercise_type",
    type=click.Choice([e.value for e in ExerciseType], case_sensitive=False),
    default=ExerciseType.TDE.value,
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
@click.option(
    "--section",
    type=str,
    default="00",
    help="Section code: 01, A0, D0",
)
@click.option("--exercise-num", type=int, default=None, help="Exercise number.")
@with_schema_guard
def create(
    output_dir: str,
    exercise_type: str,
    difficulty: str,
    taxonomy_level: str,
    taxonomy_domain: str,
    section: str,
    tag: tuple[str, ...],
    book: str | None,
    chapter: int | None,
    exercise_num: int | None,
) -> None:
    """Create a new exercise placeholder .tex file."""
    out = Path(output_dir)
    engine = _get_engine(click.get_current_context())

    if book is not None:
        _test_bib_entry_existence(engine, book)

    result = generate_exercise_file(
        out,
        exercise_type=exercise_type,
        difficulty=difficulty,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
        tags=list(tag) if tag else None,
        book_cite=book,
        chapter=chapter,
        section=section,
        exercise_num=exercise_num,
    )
    if result.created:
        click.echo(f"Created: {result.file_path}")
        copy_to_clipboard(f"\n\\input{{{result.file_path.absolute()}}}")
        engine = _get_engine(click.get_current_context())
        _sync_files(engine, [result.file_path])
    else:
        click.echo(f"Skipped (already exists): {result.file_path}")


@exercise.command(name="create-range")
@click.option("--output-dir", "-d", type=click.Path(), required=True)
@click.option("--book", type=str, required=True, help="Book citation key.")
@click.option("--chapter", type=int, required=True, help="Chapter number.")
@click.option(
    "--section",
    type=str,
    required=True,
    help="Section code: 01, A0, D0",
)
@click.option("--first", type=int, required=True, help="First exercise number.")
@click.option(
    "--last", type=int, required=True, help="Last exercise number (inclusive)."
)
@click.option(
    "--type",
    "exercise_type",
    type=click.Choice(_EXERCISE_TYPES, case_sensitive=False),
    default=ExerciseType.TDE.value,
    show_default=True,
)
@click.option(
    "--difficulty",
    type=click.Choice(_DIFFICULTIES, case_sensitive=False),
    default="medium",
    show_default=True,
)
@click.option(
    "--taxonomy-level",
    type=str,
    default="Usar-Aplicar",
    show_default=True,
)
@click.option(
    "--taxonomy-domain",
    type=str,
    default="Procedimiento Mental",
    show_default=True,
)
@click.option("--tag", multiple=True, help="Tag (repeatable).")
@with_schema_guard
def create_range(
    output_dir: str,
    book: str,
    chapter: int,
    section: str,
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
        section=section,
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

    inset_txt = ""
    for r in created:
        click.echo(f"  [created] {r.file_path.name}")
        inset_txt += f"\n\\input{{{r.file_path.absolute()}}}"
    copy_to_clipboard(inset_txt)
    for r in skipped:
        click.echo(f"  [skipped] {r.file_path.name}")
    engine = _get_engine(click.get_current_context())
    _sync_files(engine, [p.file_path for p in results])

    click.echo(
        f"\nDone: {len(created)} created, {len(skipped)} skipped "
        f"({len(results)} total)."
    )


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
@with_schema_guard
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

    exercises, source_dirs, skipped = parse_and_filter(files, status, tag)

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
@click.option(
    "--balanceo",
    is_flag=True,
    default=False,
    help=(
        "Compute a taxonomy x concept balance report over the assembled "
        "selection (stderr table, or --json for the structured form)."
    ),
)
@click.option(
    "--balanceo-csv",
    "balanceo_csv",
    type=click.Path(),
    default=None,
    help="Write the balance report as CSV to PATH (implies --balanceo).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the balance report as JSON to stdout (requires --balanceo/--balanceo-csv).",
)
@click.option(
    "--fail-under",
    "fail_under",
    type=float,
    default=None,
    help=(
        "Exit 2 if concept coverage ratio (distinct_covered/total_concepts) "
        "falls below this threshold (requires --balanceo/--balanceo-csv)."
    ),
)
@click.pass_context
@with_schema_guard
def build_exam_cmd(
    ctx,
    taxonomy_level: tuple[str, ...],
    taxonomy_domain: tuple[str, ...],
    count: int,
    points: float,
    title: str,
    instructions: str,
    output: str | None,
    balanceo: bool,
    balanceo_csv: str | None,
    as_json: bool,
    fail_under: float | None,
) -> None:
    """Build an exam by selecting exercises from the bank.

    Each --taxonomy-level creates a slot. Pair --taxonomy-domain values
    positionally with levels (missing domains default to empty string).

    ``--balanceo`` (bare) prints a taxonomy x concept balance table to
    stderr; ``--balanceo-csv PATH`` writes the same report as CSV to PATH
    (either form triggers the computation). ``--json`` (combinable) emits
    the balance report as the sole JSON object on stdout instead of the
    stderr table — the assembled .tex body is then only available via
    ``--output`` (mixing free-form .tex with a JSON stdout stream would
    corrupt the JSON). ``--fail-under FLOAT`` requires balance computation
    to be enabled and exits 2 when coverage falls below the threshold.
    """
    do_balance = balanceo or balanceo_csv is not None
    _validate_balance_flags(as_json, fail_under, do_balance)

    engine = _get_engine(ctx)
    slots = _build_exam_slots(taxonomy_level, taxonomy_domain, count, points)

    with Session(engine) as session:
        repo = SqlExerciseRepo(session)
        pool = repo.find_by_filters(status="complete", limit=10_000)
        selection = select_exercises(slots, pool)
        doc = build_exam(selection, title=title, instructions=instructions)
        report = compute_balance(selection, pool, session) if do_balance else None

    _emit_exam_warnings(doc, selection)
    if do_balance:
        _emit_balance_report(report, balanceo_csv=balanceo_csv, as_json=as_json)
    _emit_tex_body(doc, output=output, suppress=do_balance and as_json)

    if fail_under is not None and coverage_ratio(report) < fail_under:
        ctx.exit(2)


def _validate_balance_flags(as_json: bool, fail_under: float | None, do_balance: bool) -> None:
    """Fail loud when --json/--fail-under are given without a balance trigger."""
    if as_json and not do_balance:
        raise click.ClickException(
            "--json requires --balanceo or --balanceo-csv for build-exam."
        )
    if fail_under is not None and not do_balance:
        raise click.ClickException(
            "--fail-under requires --balanceo or --balanceo-csv for build-exam."
        )


def _build_exam_slots(
    taxonomy_level: tuple[str, ...],
    taxonomy_domain: tuple[str, ...],
    count: int,
    points: float,
) -> list[ExerciseSlot]:
    """Pair --taxonomy-level values with --taxonomy-domain values by index."""
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
    return slots


def _emit_exam_warnings(doc, selection) -> None:
    """Print exam-assembly warnings to stderr (unchanged pre-balance behavior)."""
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


def _emit_balance_report(report, *, balanceo_csv: str | None, as_json: bool) -> None:
    """Write the CSV (if requested) and print the table or JSON form of the report."""
    if balanceo_csv:
        write_balance_csv(report, Path(balanceo_csv))
        click.echo(f"Balance CSV written to {balanceo_csv}", err=True)

    if as_json:
        import json as _json

        click.echo(_json.dumps(balance_to_dict(report), indent=2))
    else:
        click.echo(format_human_table(report), err=True)


def _emit_tex_body(doc, *, output: str | None, suppress: bool) -> None:
    """Write/print the assembled .tex body, suppressing stdout when JSON owns it."""
    if output:
        out_path = Path(output)
        out_path.write_text(doc.content, encoding="utf-8")
        click.echo(f"Exam written to {out_path}", err=suppress)
    elif suppress:
        click.echo(
            "[INFO] .tex body suppressed on stdout under --json without "
            "--output; combine with --output to save it.",
            err=True,
        )
    else:
        click.echo(doc.content)


# ── register / register-batch ────────────────────────────────────────────────

_REGISTER_TYPES = _EXERCISE_TYPES  # same extended list


def _register_one(
    session: Any,
    tex_path: Path,
    exercise_type: str,
    course: str,
    cycle: str,
    partial: str,
    points: int,
    taxonomy_level: str | None,
    taxonomy_domain: str | None,
) -> dict[str, Any]:
    """Parse and register a single .tex file. Returns a result dict.

    Raises click.ClickException on collision or parse failure.
    """
    import json as _json
    from workflow.exercise.service import file_hash as _file_hash

    if not tex_path.exists():
        raise click.ClickException(f"File not found: {tex_path}")

    text = tex_path.read_text(encoding="utf-8")
    parse_result = parse_exercise(text, source_path=str(tex_path))

    if parse_result.errors:
        raise click.ClickException(
            f"Parse error in {tex_path.name}: {parse_result.errors[0]}"
        )

    ex_parsed = parse_result.exercise
    exercise_id: str = (
        ex_parsed.metadata.id
        if ex_parsed.metadata and ex_parsed.metadata.id
        else tex_path.stem
    )

    repo = SqlExerciseRepo(session)
    existing = repo.get_by_exercise_id(exercise_id)
    if existing is not None:
        raise click.ClickException(
            f"Exercise '{exercise_id}' already registered (source: {existing.source_path})"
        )

    # Build tags list: course first, then cycle/partial
    tags = [course, cycle, partial]
    tags_json = _json.dumps(tags)

    new_ex = Exercise(
        exercise_id=exercise_id,
        source_path=str(tex_path),
        file_hash=_file_hash(tex_path),
        status=ex_parsed.status or "complete",
        type=exercise_type,
        difficulty=(ex_parsed.metadata.difficulty if ex_parsed.metadata else None),
        taxonomy_level=taxonomy_level
        or (ex_parsed.metadata.taxonomy_level if ex_parsed.metadata else None),
        taxonomy_domain=taxonomy_domain
        or (ex_parsed.metadata.taxonomy_domain if ex_parsed.metadata else None),
        tags=tags_json,
        default_grade=float(points),
        option_count=len(ex_parsed.options),
    )
    session.add(new_ex)
    session.flush()

    return {
        "id": exercise_id,
        "registered": True,
        "db_row_id": new_ex.id,
        "path": str(tex_path),
        "course": course,
        "cycle": cycle,
        "partial": partial,
        "type": exercise_type,
    }


@exercise.command()
@click.option("--path", required=True, type=str, help="Path to existing .tex file.")
@click.option(
    "--type",
    "exercise_type",
    required=True,
    type=click.Choice(_REGISTER_TYPES, case_sensitive=False),
    help="Exercise type.",
)
@click.option("--course", required=True, type=str, help="Course code (e.g. CB0009).")
@click.option("--cycle", required=True, type=str, help="Academic cycle (e.g. 2026C1).")
@click.option("--partial", required=True, type=str, help="Parcial ID (e.g. P02).")
@click.option("--points", required=True, type=int, help="Point value.")
@click.option(
    "--taxonomy-level", type=str, default=None, help="Override taxonomy level."
)
@click.option(
    "--taxonomy-domain", type=str, default=None, help="Override taxonomy domain."
)
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Emit JSON output."
)
@click.pass_context
@with_schema_guard
def register(
    ctx,
    path: str,
    exercise_type: str,
    course: str,
    cycle: str,
    partial: str,
    points: int,
    taxonomy_level: str | None,
    taxonomy_domain: str | None,
    as_json: bool,
) -> None:
    """Register an existing .tex file into the exercise bank."""
    import json as _json

    tex_path = Path(path)
    engine = _get_engine(ctx)

    with Session(engine) as session:
        row = _register_one(
            session,
            tex_path,
            exercise_type,
            course,
            cycle,
            partial,
            points,
            taxonomy_level,
            taxonomy_domain,
        )
        session.commit()

    if as_json:
        click.echo(_json.dumps([row], indent=2))
    else:
        click.echo(f"Registered: {row['id']} (db_row_id={row['db_row_id']})")


@exercise.command(name="register-batch")
@click.argument("glob_pattern")
@click.option("--course", required=True, type=str, help="Course code (e.g. CB0009).")
@click.option("--cycle", required=True, type=str, help="Academic cycle (e.g. 2026C1).")
@click.option("--partial", required=True, type=str, help="Parcial ID (e.g. P02).")
@click.option(
    "--points", type=int, default=1, show_default=True, help="Point value per exercise."
)
@click.option(
    "--type",
    "exercise_type",
    type=click.Choice(_REGISTER_TYPES, case_sensitive=False),
    default=None,
    help="Override exercise type for all files.",
)
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Emit JSON output."
)
@click.pass_context
@with_schema_guard
def register_batch(
    ctx,
    glob_pattern: str,
    course: str,
    cycle: str,
    partial: str,
    points: int,
    exercise_type: str | None,
    as_json: bool,
) -> None:
    """Register multiple existing .tex files matching a glob pattern."""
    import glob as _glob
    import json as _json

    matched = sorted(_glob.glob(glob_pattern))
    if not matched:
        raise click.ClickException(f"No files matched glob: {glob_pattern}")

    engine = _get_engine(ctx)
    results: list[dict[str, Any]] = []

    with Session(engine) as session:
        for path_str in matched:
            tex_path = Path(path_str)
            # Infer type from .tex metadata if not overridden
            inferred_type = exercise_type
            if inferred_type is None:
                text = tex_path.read_text(encoding="utf-8") if tex_path.exists() else ""
                pr = parse_exercise(text, source_path=path_str)
                if pr.exercise and pr.exercise.metadata and pr.exercise.metadata.type:
                    inferred_type = pr.exercise.metadata.type
                else:
                    inferred_type = "essay"

            row = _register_one(
                session,
                tex_path,
                inferred_type,
                course,
                cycle,
                partial,
                points,
                None,
                None,
            )
            results.append(row)
        session.commit()

    if as_json:
        click.echo(_json.dumps(results, indent=2))
    else:
        for row in results:
            click.echo(f"Registered: {row['id']} (db_row_id={row['db_row_id']})")
        click.echo(f"\nTotal: {len(results)} exercise(s) registered.")
