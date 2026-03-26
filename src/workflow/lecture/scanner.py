"""Lecture directory scanner — Phase 5a.

Discovers .tex files in a LectureInstance's directory structure and
registers them as Notes in the local slipbox.db.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning a lecture directory."""

    discovered: tuple[str, ...]
    registered: tuple[str, ...]
    already_registered: tuple[str, ...]
    warnings: tuple[str, ...]


def scan_lecture_directory(
    lecture_dir: Path,
    *,
    subdirs: tuple[str, ...] = ("lect/tex", "eval/tex"),
) -> list[Path]:
    """Find all .tex files in lecture subdirectories.

    Searches in {lecture_dir}/{subdir}/**/*.tex for each subdir.
    Returns sorted list of absolute paths.
    """
    found: list[Path] = []
    for subdir in subdirs:
        target = lecture_dir / subdir
        if not target.exists():
            continue
        found.extend(target.rglob("*.tex"))
    return sorted(found)


def generate_note_reference(filepath: Path, lecture_dir: Path) -> str:
    """Generate a note reference from a file path.

    Format: relative path from lecture_dir with / replaced by -,
    without the .tex extension.

    Example: lect/tex/tema01/intro.tex → lect-tex-tema01-intro
    """
    rel = filepath.relative_to(lecture_dir)
    # Drop the suffix and join parts with dash
    parts = list(rel.parts)
    # Remove extension from the last part
    parts[-1] = Path(parts[-1]).stem
    return "-".join(parts)


def register_notes(
    lecture_dir: Path,
    session: Session,
    *,
    subdirs: tuple[str, ...] = ("lect/tex", "eval/tex"),
) -> ScanResult:
    """Scan lecture_dir and register discovered .tex files as Notes.

    Uses the provided SQLAlchemy session against a local slipbox.db.
    Returns a ScanResult with counts for reporting.
    """
    from workflow.db.models.notes import Note
    from sqlalchemy import select

    tex_files = scan_lecture_directory(lecture_dir, subdirs=subdirs)

    discovered: list[str] = []
    registered: list[str] = []
    already_registered: list[str] = []
    warnings: list[str] = []

    # Pre-load all existing filenames in one query to avoid N+1
    existing: set[str] = set(session.scalars(select(Note.filename)).all())

    for filepath in tex_files:
        filename = str(filepath)
        reference = generate_note_reference(filepath, lecture_dir)
        discovered.append(filename)

        if filename in existing:
            already_registered.append(filename)
        else:
            note = Note(filename=filename, reference=reference)
            session.add(note)
            registered.append(filename)

    session.flush()

    return ScanResult(
        discovered=tuple(discovered),
        registered=tuple(registered),
        already_registered=tuple(already_registered),
        warnings=tuple(warnings),
    )
