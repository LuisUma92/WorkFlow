"""Lecture reference extractor and linker — Phase 5b.

Scans lecture .tex files for cross-references and citations, then updates
the Citation, Label, and Link tables in the local slipbox.db.

Design:
- extract_references() is pure (no I/O, no DB): takes raw text, returns list
- link_lecture_files() is the DB integration layer
- Both are idempotent: running twice yields the same DB state
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


# ── Regular expressions ──────────────────────────────────────────────────────

# Match \cite{key1,key2,...} — capture the raw key list
_CITE_RE = re.compile(r"\\cite\{([^}]+)\}")

# Match \label{name}
_LABEL_RE = re.compile(r"\\label\{([^}]+)\}")

# Match \ref{name} and \eqref{name}
_REF_RE = re.compile(r"\\(?:eq)?ref\{([^}]+)\}")

# Match \input{path}
_INPUT_RE = re.compile(r"\\input\{([^}]+)\}")


# ── Domain objects ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractedReference:
    """A reference found in a .tex file."""

    ref_type: str       # "cite", "ref", "label", "input"
    key: str            # citation key or label name or input path
    source_file: str    # file path that contained the reference
    line_number: int    # 1-based line number where reference appears


@dataclass(frozen=True)
class LinkResult:
    """Result of linking lecture files."""

    references_found: int
    citations_found: int
    links_created: int
    citations_created: int
    warnings: tuple[str, ...]


# ── Pure extraction ──────────────────────────────────────────────────────────


def _strip_comment(line: str) -> str:
    """Return the portion of *line* before the first unescaped ``%``."""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\":
            i += 2  # skip escaped character
            continue
        if ch == "%":
            return line[:i]
        i += 1
    return line


def extract_references(text: str, source_file: str = "") -> list[ExtractedReference]:
    """Extract all cross-references and citations from LaTeX text.

    Looks for:
    - ``\\cite{key1,key2}``  → one ExtractedReference per key, type="cite"
    - ``\\ref{label}``       → type="ref"
    - ``\\eqref{label}``     → type="ref"
    - ``\\label{name}``      → type="label"
    - ``\\input{path}``      → type="input"

    Comments (text after an unescaped ``%``) are stripped before matching.

    Parameters
    ----------
    text:
        Raw LaTeX source (may be multi-line).
    source_file:
        Path string stored verbatim in each ExtractedReference.

    Returns
    -------
    list[ExtractedReference]
        All references found, in order of appearance (top-down, left-right).
    """
    refs: list[ExtractedReference] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line)

        # \cite{key1, key2, ...}
        for m in _CITE_RE.finditer(line):
            for raw_key in m.group(1).split(","):
                key = raw_key.strip()
                if key:
                    refs.append(
                        ExtractedReference(
                            ref_type="cite",
                            key=key,
                            source_file=source_file,
                            line_number=line_no,
                        )
                    )

        # \label{name}
        for m in _LABEL_RE.finditer(line):
            refs.append(
                ExtractedReference(
                    ref_type="label",
                    key=m.group(1).strip(),
                    source_file=source_file,
                    line_number=line_no,
                )
            )

        # \ref{} and \eqref{}
        for m in _REF_RE.finditer(line):
            refs.append(
                ExtractedReference(
                    ref_type="ref",
                    key=m.group(1).strip(),
                    source_file=source_file,
                    line_number=line_no,
                )
            )

        # \input{path}
        for m in _INPUT_RE.finditer(line):
            refs.append(
                ExtractedReference(
                    ref_type="input",
                    key=m.group(1).strip(),
                    source_file=source_file,
                    line_number=line_no,
                )
            )

    return refs


# ── DB integration ───────────────────────────────────────────────────────────


def _upsert_cite(session: Session, note_id: int, key: str) -> bool:
    """Insert a Citation if it does not already exist. Returns True if created."""
    from sqlalchemy import select

    from workflow.db.models.notes import Citation

    existing = session.scalars(
        select(Citation).where(Citation.note_id == note_id, Citation.citationkey == key)
    ).first()
    if existing is None:
        session.add(Citation(note_id=note_id, citationkey=key))
        return True
    return False


def _upsert_label(session: Session, note_id: int, label_name: str) -> None:
    """Insert a Label if it does not already exist."""
    from sqlalchemy import select

    from workflow.db.models.notes import Label

    existing = session.scalars(
        select(Label).where(Label.note_id == note_id, Label.label == label_name)
    ).first()
    if existing is None:
        session.add(Label(note_id=note_id, label=label_name))


def _upsert_link(session: Session, source_id: int, target_label_id: int) -> bool:
    """Insert a Link if it does not already exist. Returns True if created."""
    from sqlalchemy import select

    from workflow.db.models.notes import Link

    existing = session.scalars(
        select(Link).where(Link.source_id == source_id, Link.target_id == target_label_id)
    ).first()
    if existing is None:
        session.add(Link(source_id=source_id, target_id=target_label_id))
        return True
    return False


def _process_labels_and_citations(tex_path: Path, session: Session, warnings: list[str]) -> tuple[int, int, int]:
    """Pass 1 worker: register labels and citations for one file.

    Returns (total_refs, total_cites, citations_created).
    """
    from sqlalchemy import select

    from workflow.db.models.notes import Note

    filename = str(tex_path)
    try:
        text = tex_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.append(f"Cannot read {tex_path}: {exc}")
        return 0, 0, 0

    note: Note | None = session.scalars(
        select(Note).where(Note.filename == filename)
    ).first()

    if note is None:
        warnings.append(
            f"File not registered as a Note (run 'lecture scan' first): {filename}"
        )
        return 0, 0, 0

    refs = extract_references(text, source_file=filename)
    total_cites = 0
    citations_created = 0

    for ref in refs:
        if ref.ref_type == "cite":
            total_cites += 1
            if _upsert_cite(session, note.id, ref.key):
                citations_created += 1
        elif ref.ref_type == "label":
            _upsert_label(session, note.id, ref.key)

    session.flush()
    return len(refs), total_cites, citations_created


def _process_refs(tex_path: Path, session: Session, warnings: list[str]) -> int:
    """Pass 2 worker: resolve \\ref{} → Link rows for one file.

    Returns links_created count.
    """
    from sqlalchemy import select

    from workflow.db.models.notes import Label, Note

    filename = str(tex_path)
    note: Note | None = session.scalars(
        select(Note).where(Note.filename == filename)
    ).first()
    if note is None:
        return 0

    try:
        text = tex_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    links_created = 0
    for ref in extract_references(text, source_file=filename):
        if ref.ref_type != "ref":
            continue
        target_label = session.scalars(
            select(Label).where(Label.label == ref.key)
        ).first()
        if target_label is None:
            warnings.append(f"Dangling \\ref{{{ref.key}}} in {filename}:{ref.line_number}")
            continue
        if _upsert_link(session, note.id, target_label.id):
            links_created += 1

    session.flush()
    return links_created


def link_lecture_files(tex_files: list[Path], session: Session) -> LinkResult:
    """Scan tex files for references and update Citation/Label/Link tables.

    Algorithm
    ---------
    For each file (must already be registered as a Note in the DB):

    1. ``\\label{name}``  → upsert a Label row linked to the file's Note.
    2. ``\\cite{key}``    → upsert a Citation row linked to the file's Note.
    3. ``\\ref{name}``    → find the Label by name; if found, upsert a Link
                            from the file's Note to that Label.  If not found,
                            emit a warning (dangling reference).

    All operations are idempotent: duplicate rows are never created.

    Parameters
    ----------
    tex_files:
        Absolute paths to .tex files to process.
    session:
        SQLAlchemy session connected to a local slipbox.db.

    Returns
    -------
    LinkResult
        Summary counts and any warnings generated.
    """
    warnings: list[str] = []
    total_refs = 0
    total_cites = 0
    links_created = 0
    citations_created = 0

    # Pass 1: labels and citations (must come before Pass 2 so labels exist)
    for tex_path in tex_files:
        refs, cites, created = _process_labels_and_citations(tex_path, session, warnings)
        total_refs += refs
        total_cites += cites
        citations_created += created

    # Pass 2: resolve \ref{} → Link rows
    for tex_path in tex_files:
        links_created += _process_refs(tex_path, session, warnings)

    return LinkResult(
        references_found=total_refs,
        citations_found=total_cites,
        links_created=links_created,
        citations_created=citations_created,
        warnings=tuple(warnings),
    )


__all__ = ["ExtractedReference", "LinkResult", "extract_references", "link_lecture_files"]
