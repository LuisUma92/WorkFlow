"""Exercise service functions — business logic extracted from CLI.

Provides pure functions that CLI commands delegate to.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from workflow.db.models.exercises import Exercise, ExerciseOption
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.parser import parse_exercise

if TYPE_CHECKING:
    from workflow.exercise.domain import ParsedExercise


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


def file_hash(path: Path) -> str:
    """SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_exercises(
    session: Session,
    files: list[Path],
    max_file_bytes: int = _MAX_FILE_BYTES,
) -> tuple[SyncResult, list[str]]:
    """Sync .tex files to DB. Returns (result, log_messages)."""
    repo = SqlExerciseRepo(session)

    new_count = 0
    updated_count = 0
    unchanged_count = 0
    skipped_count = 0
    messages: list[str] = []

    for filepath in files:
        if filepath.stat().st_size > max_file_bytes:
            messages.append(f"  [SKIP] {filepath.name}: file too large")
            skipped_count += 1
            continue

        text = filepath.read_text(encoding="utf-8")
        result = parse_exercise(text, source_path=str(filepath))

        if result.errors:
            messages.append(f"  [SKIP] {filepath.name}: {result.errors[0]}")
            skipped_count += 1
            continue

        ex = result.exercise
        if ex.metadata is None:
            messages.append(f"  [SKIP] {filepath.name}: no metadata")
            skipped_count += 1
            continue

        current_hash = file_hash(filepath)

        existing = repo.get_by_exercise_id(ex.metadata.id)

        if existing is not None and existing.file_hash == current_hash:
            unchanged_count += 1
            continue

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

        messages.append(f"  [{status_label}] {ex.metadata.id}: {ex.status}")

    session.commit()

    return SyncResult(
        new=new_count,
        updated=updated_count,
        unchanged=unchanged_count,
        skipped=skipped_count,
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
