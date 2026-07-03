"""Exercise service functions — business logic extracted from CLI.

Provides pure functions that CLI commands delegate to.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from sqlalchemy.orm import Session

from workflow.concept.service import resolve_concepts
from workflow.db.models.exercises import Exercise, ExerciseConcept, ExerciseOption
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.parser import INVALID_STATUS_ERROR_PREFIX, parse_exercise
from workflow.bibliography.service import get_bib_entry_by_bibkey, BibKeyAmbiguous

if TYPE_CHECKING:
    from workflow.exercise.domain import ParsedExercise

logger = logging.getLogger(__name__)


_MAX_FILE_BYTES = 10 * 1024 * 1024

__all__ = [
    "SyncResult",
    "file_hash",
    "sync_exercises",
    "gc_orphans",
    "delete_orphans",
    "parse_and_filter",
    "_MAX_FILE_BYTES",
]


@dataclass(frozen=True)
class SyncResult:
    new: int
    updated: int
    unchanged: int
    skipped: int
    invalid_status: int = 0  # files skipped due to an invalid explicit `status:`
    dropped_concepts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def file_hash(path: Path) -> str:
    """SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_book_id(
    session: Session,
    bibkey: str | None,
    filename: str,
    messages: list[str],
) -> int | None:
    """Resolve a bibkey to a BibEntry id for the exercise's ``book_id``.

    Treats a missing or ambiguous bibkey as a soft, non-fatal data-quality
    warning (``messages`` collects it) and returns ``None`` so the exercise
    record is still synced with a null ``book_id``.
    """
    if bibkey is None:
        return None
    try:
        bib = get_bib_entry_by_bibkey(session, bibkey)
    except BibKeyAmbiguous:
        messages.append(
            f"  [WARN] {filename}: ambiguous bibkey '{bibkey}'"
            " — multiple entries match; book_id set to null."
        )
        return None
    return bib.id if bib is not None else None


def _sync_exercise_concepts(
    session: Session,
    result_record: Exercise,
    concept_codes: list[str],
    filename: str,
    strict_concepts: bool,
    messages: list[str],
    concept_errors: list[str],
) -> list[str]:
    """Resolve + upsert ExerciseConcept M2M rows for one exercise's concept slugs.

    Unresolved codes are tagged with *filename* and routed to *concept_errors*
    (strict) or appended to *messages* as a warning (lenient) — never raised
    here so the caller can finish the whole batch before deciding to abort.

    Returns the list of concept codes that could not be resolved (dropped),
    regardless of strict/lenient mode, for structured reporting by the caller.
    """
    found_concepts, issues = resolve_concepts(concept_codes, session, strict=strict_concepts)
    for issue in issues:
        tagged_message = f"{filename}: {issue['message']}"
        if issue["severity"] == "error":
            concept_errors.append(tagged_message)
        else:
            messages.append(f"  [WARN] {tagged_message}")
            logger.warning("%s", tagged_message)

    found_codes = {c.code for c in found_concepts}
    dropped_codes = [code for code in concept_codes if code not in found_codes]

    desired_ids = {c.id for c in found_concepts}
    existing_ids = {ec.concept_id for ec in result_record.concept_links}
    for c in found_concepts:
        if c.id not in existing_ids:
            session.add(ExerciseConcept(exercise_id=result_record.id, concept_id=c.id))
    for ec in list(result_record.concept_links):
        if ec.concept_id not in desired_ids:
            session.delete(ec)

    return dropped_codes


@dataclass(frozen=True)
class _SkipReason:
    """A reason a file was skipped during sync, plus reporting hints."""

    message: str
    is_invalid_status: bool = False
    report_as_error: bool = True


def _prefilter_file(
    filepath: Path,
    max_file_bytes: int,
    status_filter: str | None,
) -> tuple["ParsedExercise | None", _SkipReason | None]:
    """Parse+validate one file before it's eligible for sync.

    Returns ``(parsed_exercise, None)`` if the file should proceed, or
    ``(None, skip_reason)`` if it should be skipped.
    """
    if filepath.stat().st_size > max_file_bytes:
        return None, _SkipReason("file too large")

    text = filepath.read_text(encoding="utf-8")
    result = parse_exercise(text, source_path=str(filepath))

    if result.errors:
        invalid = any(
            err.startswith(INVALID_STATUS_ERROR_PREFIX) for err in result.errors
        )
        return None, _SkipReason(result.errors[0], is_invalid_status=invalid)

    ex = result.exercise
    if ex.metadata is None:
        return None, _SkipReason("no metadata")

    if status_filter is not None and ex.status != status_filter:
        return None, _SkipReason(
            f"status '{ex.status}' != filter '{status_filter}'",
            report_as_error=False,
        )

    return ex, None


def _build_and_upsert_exercise(
    session: Session,
    repo: SqlExerciseRepo,
    filepath: Path,
    ex: "ParsedExercise",
    resolved_path: str,
    current_hash: str,
    bib_entry_id: int | None,
) -> Exercise:
    """Build an Exercise ORM row from a parsed exercise and upsert it."""
    tags_json = json.dumps(ex.metadata.tags) if ex.metadata.tags else None

    exercise_record = Exercise(
        exercise_id=ex.metadata.id,
        source_path=resolved_path,
        file_hash=current_hash,
        status=ex.status,
        type=ex.metadata.type,
        difficulty=ex.metadata.difficulty,
        taxonomy_level=ex.metadata.taxonomy_level,
        taxonomy_domain=ex.metadata.taxonomy_domain,
        tags=tags_json,
        default_grade=ex.default_grade,
        has_images=len(ex.image_refs) > 0,
        image_refs=json.dumps(list(ex.image_refs)) if ex.image_refs else None,
        diagram_id=ex.diagram_id,
        option_count=len(ex.options),
        book_id=bib_entry_id,
    )

    result_record = repo.upsert(exercise_record)

    result_record.options.clear()
    for opt in ex.options:
        result_record.options.append(
            ExerciseOption(
                label=opt.label,
                is_correct=opt.is_correct,
                sort_order=ord(opt.label) - ord("a"),
            )
        )

    return result_record


def _sync_one_file(
    session: Session,
    repo: SqlExerciseRepo,
    filepath: Path,
    ex: "ParsedExercise",
    strict_concepts: bool,
    messages: list[str],
    concept_errors: list[str],
) -> dict[str, Any]:
    """Upsert one already-prefiltered exercise. Returns an outcome dict.

    ``{"outcome": "unchanged" | "new" | "updated", "dropped_codes": list[str]}``
    """
    current_hash = file_hash(filepath)
    resolved_path = str(filepath.resolve())
    existing = repo.get_by_exercise_id(ex.metadata.id)
    if existing is not None:
        content_unchanged = existing.file_hash == current_hash
        path_changed = existing.source_path != resolved_path
        if content_unchanged and not path_changed:
            return {"outcome": "unchanged", "dropped_codes": []}

    bib_entry_id = _resolve_book_id(session, ex.book_cite, filepath.name, messages)

    result_record = _build_and_upsert_exercise(
        session, repo, filepath, ex, resolved_path, current_hash, bib_entry_id
    )

    concept_codes: list[str] = ex.metadata.concepts or []
    dropped_codes = _sync_exercise_concepts(
        session,
        result_record,
        concept_codes,
        filepath.name,
        strict_concepts,
        messages,
        concept_errors,
    )

    outcome = "updated" if existing is not None else "new"
    messages.append(f"  [{outcome}] {ex.metadata.id}: {ex.status}")
    return {"outcome": outcome, "dropped_codes": dropped_codes}


def sync_exercises(
    session: Session,
    files: list[Path],
    max_file_bytes: int = _MAX_FILE_BYTES,
    strict_concepts: bool = False,
    status_filter: str | None = None,
    dry_run: bool = False,
) -> tuple[SyncResult, list[str]]:
    """Sync .tex files to DB. Returns (result, log_messages).

    ``status_filter``, if set, restricts syncing to files whose *parsed*
    (post-inference) status matches; non-matching files are counted as
    skipped and left untouched.

    ``dry_run``, if True, performs the full parse/diff and rolls back
    instead of committing — no DB writes are persisted.
    """
    repo = SqlExerciseRepo(session)

    new_count = 0
    updated_count = 0
    unchanged_count = 0
    skipped_count = 0
    invalid_status_count = 0
    messages: list[str] = []
    concept_errors: list[str] = []  # strict-mode failures, collected across all files
    error_reports: list[str] = []  # structured skip/parse-error reasons
    dropped_concepts: list[dict[str, Any]] = []

    for filepath in files:
        ex, skip = _prefilter_file(filepath, max_file_bytes, status_filter)
        if skip is not None:
            messages.append(f"  [SKIP] {filepath.name}: {skip.message}")
            if skip.report_as_error:
                error_reports.append(f"{filepath.name}: {skip.message}")
            skipped_count += 1
            if skip.is_invalid_status:
                invalid_status_count += 1
            continue

        outcome = _sync_one_file(
            session, repo, filepath, ex, strict_concepts, messages, concept_errors
        )

        if outcome["outcome"] == "unchanged":
            unchanged_count += 1
            continue
        if outcome["outcome"] == "updated":
            updated_count += 1
        else:
            new_count += 1
        if outcome["dropped_codes"]:
            dropped_concepts.append(
                {"file": filepath.name, "codes": outcome["dropped_codes"]}
            )

    if concept_errors:
        # Strict-mode failure: abort atomically, surface every dropped code.
        session.rollback()
        raise ValueError("; ".join(concept_errors))

    if dry_run:
        # Full parse/diff already computed above; discard all pending writes.
        session.rollback()
    else:
        session.commit()

    return SyncResult(
        new=new_count,
        updated=updated_count,
        unchanged=unchanged_count,
        skipped=skipped_count,
        invalid_status=invalid_status_count,
        dropped_concepts=dropped_concepts,
        errors=error_reports,
    ), messages


def gc_orphans(session: Session) -> tuple[list[str], list[str]]:
    """Find orphaned records. Returns (orphan_ids, orphan_paths)."""
    repo = SqlExerciseRepo(session)
    orphans = repo.get_orphans()
    ids = [ex.exercise_id for ex in orphans]
    paths = [ex.source_path for ex in orphans]
    return ids, paths


def delete_orphans(session: Session, exercise_ids: list[str]) -> int:
    """Delete orphaned records by ID. Returns count deleted."""
    repo = SqlExerciseRepo(session)
    count = 0
    for eid in exercise_ids:
        if repo.delete(eid):
            count += 1
    return count


def parse_and_filter(
    files: list[Path],
    status: str,
    tag: tuple[str, ...],
    max_file_bytes: int = _MAX_FILE_BYTES,
) -> tuple[list[ParsedExercise], list[Path], int]:
    """Parse .tex files and filter by status/tags.

    Returns (exercises, source_dirs, skipped_count).
    """
    from workflow.exercise.domain import ParsedExercise  # noqa: F811

    exercises: list[ParsedExercise] = []
    source_dirs: list[Path] = []
    skipped = 0

    for filepath in files:
        if filepath.stat().st_size > max_file_bytes:
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
