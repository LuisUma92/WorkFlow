"""Service for generating literature notes from PRISMA-accepted bibliography entries.

Wave C1 — single-entry accept-to-note.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.bibliography.render import entry_to_biblatex
from workflow.bibliography.service import get_bib_entry_by_bibkey
from workflow.db.models.bibliography import BibEntry, ReviewRecord
from workflow.vault.paths import resolve_vault_root

if TYPE_CHECKING:
    pass


__all__ = [
    "AcceptToNoteResult",
    "build_note",
    "accept_to_note",
]


@dataclass
class AcceptToNoteResult:
    """Result of a single accept-to-note operation."""

    note_path: Path
    bibkey: str
    created: bool
    content: str


# Allowlist for bibkey used as a filename component: reject path separators,
# traversal sequences, and any other character unsafe in a filename.
_SAFE_BIBKEY_RE = re.compile(r"^[A-Za-z0-9._-]+$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _authors_line(entry: BibEntry) -> str:
    """Return a comma-separated list of author surnames with year, or empty string."""
    surnames = [
        link.author.last_name
        for link in entry.author_links
        if link.author is not None
    ]
    year_str = str(entry.year) if entry.year else ""
    if surnames:
        names = ", ".join(surnames)
        return f"{names} ({year_str})" if year_str else names
    return year_str


def _journal_source(entry: BibEntry) -> str:
    """Return journaltitle, then booktitle, then empty string."""
    return entry.journaltitle or entry.booktitle or ""


def _build_frontmatter(
    entry: BibEntry,
    record: ReviewRecord | None,
    keyword_id: int | None,
    today: str,
) -> str:
    """Render YAML frontmatter between --- fences."""
    bibkey = entry.bibkey or ""
    note_id = f"{today.replace('-', '')}-lit-{bibkey}"
    title = (entry.title or "").replace('"', '\\"')

    record_id_val = record.id if record is not None else "null"
    kw_id_val = keyword_id if keyword_id is not None else "null"
    origin = "prisma" if record is not None or keyword_id is not None else "manual"

    lines = [
        "---",
        f'id: "{note_id}"',
        f'title: "{title}"',
        "type: literature",
        f"bibkey: {bibkey}",
        f"prisma_review_record_id: {record_id_val}",
        f"prisma_keyword_id: {kw_id_val}",
        "main_topic_id: null",
        "concepts: []",
        "tags: []",
        f'created: "{today}"',
        f"origin: {origin}",
        "---",
    ]
    return "\n".join(lines)


def _build_metadata_section(entry: BibEntry) -> str:
    """Render the ## Metadata section."""
    authors_line = _authors_line(entry)
    journal = _journal_source(entry)
    year_str = str(entry.year) if entry.year else ""

    lines = ["## Metadata", ""]
    lines.append(f"- **Authors**: {authors_line}")
    lines.append(f"- **Journal/Source**: {journal}")
    if entry.doi:
        lines.append(f"- **DOI**: https://doi.org/{entry.doi}")
    lines.append(f"- **Year**: {year_str}")
    return "\n".join(lines)


def _build_rationale_section(record: ReviewRecord, session: Session) -> str:
    """Render the ## PRISMA rationale section (only when record is not None)."""
    # Reload rationale_links to ensure they are populated
    session.refresh(record)

    keyword_label = record.keyword.keyword_list if record.keyword else "(unknown keyword)"
    lines = [
        "## PRISMA rationale",
        "",
        f"> Keyword: {keyword_label} — review record {record.id}",
    ]

    if record.include_rationale:
        lines.append("")
        lines.append(record.include_rationale)

    option_labels = [
        link.rationale_option.rationale_argument
        for link in record.rationale_links
        if link.rationale_option is not None
        and link.rationale_option.rationale_argument is not None
    ]
    if option_labels:
        lines.append("")
        for label in option_labels:
            lines.append(f"- {label}")

    return "\n".join(lines)


def build_note(session: Session, entry: BibEntry, record: ReviewRecord | None) -> str:
    """Render a literature note as a markdown string.

    Args:
        session: Active SQLAlchemy session (needed to resolve rationale_links).
        entry: The BibEntry to render.
        record: The ReviewRecord providing PRISMA context, or None.

    Returns:
        Full markdown content including YAML frontmatter.
    """
    today = date.today().isoformat()
    keyword_id: int | None = record.keyword_id if record is not None else None

    frontmatter = _build_frontmatter(entry, record, keyword_id, today)
    title_line = f"# {entry.title or ''}"
    metadata = _build_metadata_section(entry)

    sections = [frontmatter, "", title_line, "", metadata]

    if record is not None:
        sections.append("")
        sections.append(_build_rationale_section(record, session))

    sections += [
        "",
        "## Notes",
        "",
        "<!-- Your reading notes here -->",
        "",
        "## Bib block",
        "",
        "```bib",
        entry_to_biblatex(entry),
        "```",
        "",
    ]

    return "\n".join(sections)


def _resolve_entry(
    session: Session,
    bibkey: str | None,
    bib_entry_id: int | None,
) -> BibEntry:
    """Resolve a BibEntry by id or bibkey. Raises ValueError if not found."""
    if bib_entry_id is not None:
        entry = session.get(BibEntry, bib_entry_id)
        if entry is None:
            raise ValueError(f"No BibEntry found with id={bib_entry_id}")
        return entry

    if bibkey is not None:
        # May raise BibKeyAmbiguous — let it propagate to caller
        entry = get_bib_entry_by_bibkey(session, bibkey)
        if entry is None:
            raise ValueError(f"No BibEntry found with bibkey={bibkey!r}")
        return entry

    raise ValueError("Either bibkey or bib_entry_id must be provided")


def _resolve_record(
    session: Session,
    entry: BibEntry,
    review_record_id: int | None,
    keyword_id: int | None,
) -> ReviewRecord | None:
    """Resolve a ReviewRecord or return None if no PRISMA context requested."""
    if review_record_id is not None:
        record = session.get(ReviewRecord, review_record_id)
        if record is None:
            raise ValueError(
                f"No ReviewRecord found with id={review_record_id}"
            )
        return record

    if keyword_id is not None:
        stmt = select(ReviewRecord).where(
            ReviewRecord.keyword_id == keyword_id,
            ReviewRecord.bib_entry_id == entry.id,
        )
        return session.scalars(stmt).first()

    return None


def accept_to_note(
    session: Session,
    *,
    bibkey: str | None = None,
    bib_entry_id: int | None = None,
    keyword_id: int | None = None,
    review_record_id: int | None = None,
    vault_root: Path | None = None,
    dry_run: bool = False,
) -> AcceptToNoteResult:
    """Generate (or find existing) literature note for a bibliography entry.

    Args:
        session: Active SQLAlchemy session.
        bibkey: BibEntry bibkey (raises BibKeyAmbiguous if non-unique).
        bib_entry_id: Disambiguates when bibkey is non-unique.
        keyword_id: Resolve ReviewRecord via (keyword_id, bib_entry_id) pair.
        review_record_id: Directly reference a ReviewRecord.
        vault_root: Override vault root (default: resolve_vault_root()).
        dry_run: Compute content but do not write file.

    Returns:
        AcceptToNoteResult with note_path, bibkey, created flag, and content.

    Raises:
        ValueError: If entry cannot be resolved.
        BibKeyAmbiguous: If bibkey matches multiple entries.
    """
    entry = _resolve_entry(session, bibkey, bib_entry_id)
    record = _resolve_record(session, entry, review_record_id, keyword_id)

    resolved_bibkey = entry.bibkey or ""
    if not _SAFE_BIBKEY_RE.match(resolved_bibkey):
        raise ValueError(
            f"bibkey {resolved_bibkey!r} contains characters unsafe for a "
            f"filename; refusing to build a note path"
        )
    today = date.today().isoformat()
    today_compact = today.replace("-", "")
    filename = f"{today_compact}-lit-{resolved_bibkey}.md"

    root = vault_root if vault_root is not None else resolve_vault_root()
    note_path = root / "notes" / "literature" / filename

    content = build_note(session, entry, record)

    if note_path.exists():
        return AcceptToNoteResult(
            note_path=note_path,
            bibkey=resolved_bibkey,
            created=False,
            content=content,
        )

    if not dry_run:
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")

    return AcceptToNoteResult(
        note_path=note_path,
        bibkey=resolved_bibkey,
        created=not dry_run,
        content=content,
    )


def accept_to_note_json(result: AcceptToNoteResult) -> str:
    """Serialize an AcceptToNoteResult to the --json wire format."""
    return json.dumps({
        "note_path": str(result.note_path),
        "bibkey": result.bibkey,
        "created": result.created,
    })
