"""workflow.notes.sync — bulk sync .md vault files into DB (Note/Label/Link rows).

File is truth; DB is index. Mirrors the lecture linker pattern.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.notes import Label, Link, Note, NoteEdge
from workflow.notes.edges import parse_relations_frontmatter
from workflow.notes.linker_ops import upsert_label, upsert_link, upsert_note_concept, upsert_note_edge
from workflow.notes.wikilinks import (
    WIKILINK_NOTE_LABEL_RE,
    WIKILINK_NOTE_LABEL_TEXT_RE,
    WIKILINK_NOTE_RE,
    WIKILINK_NOTE_TEXT_RE,
)

# Allowlist for anchor values: only safe slug characters (no path separators)
_ANCHOR_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


@dataclass
class SyncReport:
    notes_scanned: int = 0
    labels_registered: int = 0
    links_created: int = 0
    citations_registered: int = 0
    orphans_dropped: int = 0
    edges_created: int = 0
    concept_links_created: int = 0
    concept_issues: list = None  # list[dict[str, str]]

    def __post_init__(self) -> None:
        if self.concept_issues is None:
            self.concept_issues = []


def _parse_md(path: Path) -> tuple[dict[str, object], str] | None:
    """Parse frontmatter + body from a .md file.

    Returns (frontmatter_dict, body_str) or None if frontmatter is missing/invalid.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if not text.startswith("---"):
        return None

    end = text.find("\n---", 3)
    if end == -1:
        return None

    fm_raw = text[3:end].strip()
    body = text[end + 4:]

    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        return None

    if not isinstance(fm, dict):
        return None

    return fm, body


def _extract_wikilinks(body: str) -> list[tuple[str, str | None]]:
    """Return (note_ref, anchor_or_None) pairs from all wikilinks in body.

    Most-specific patterns matched first to avoid double-counting overlapping spans.
    """
    results: list[tuple[str, str | None]] = []
    consumed: set[tuple[int, int]] = set()

    def _add(
        matches: re.Iterator[re.Match[str]],
        note_group: int,
        anchor_group: int | None,
    ) -> None:
        for m in matches:
            span = m.span()
            if span in consumed:
                continue
            consumed.add(span)
            note_ref = m.group(note_group).strip()
            anchor = m.group(anchor_group).strip() if anchor_group else None
            results.append((note_ref, anchor))

    _add(WIKILINK_NOTE_LABEL_TEXT_RE.finditer(body), 1, 2)
    _add(WIKILINK_NOTE_LABEL_RE.finditer(body), 1, 2)
    _add(WIKILINK_NOTE_TEXT_RE.finditer(body), 1, None)
    _add(WIKILINK_NOTE_RE.finditer(body), 1, None)

    return results


def _upsert_note_row(
    session: Session, filename: str, fm: dict[str, object]
) -> Note:
    """Upsert a Note row; returns the persisted Note with a valid id."""
    id_value = fm["id"]  # canonical zettel identifier (frontmatter `id:`)
    title = fm.get("title") or None
    note_type = fm.get("type") or None
    now = datetime.now(tz=timezone.utc)

    existing = session.scalars(
        select(Note).where(Note.filename == filename)
    ).first()

    if existing is None:
        existing = session.scalars(
            select(Note).where(Note.zettel_id == id_value)
        ).first()

    if existing is None:
        note = Note(
            filename=filename,
            reference=id_value,   # legacy column — keep in sync with zettel_id
            zettel_id=id_value,
            title=title,
            note_type=note_type,
            last_edit_date=now,
            source_format="md",
        )
        session.add(note)
    else:
        existing.filename = filename
        existing.reference = id_value
        existing.zettel_id = id_value
        existing.title = title
        existing.note_type = note_type
        existing.last_edit_date = now
        note = existing

    session.flush()
    return note


def _upsert_note_labels(
    session: Session, note: Note, anchors: list[str]
) -> int:
    """Upsert synthetic __note__ label + frontmatter anchors. Returns new label count."""
    valid_anchors = ["__note__"] + [a for a in anchors if _ANCHOR_RE.match(a)]

    # Bulk-fetch existing labels to avoid N+1
    existing_labels = set(
        session.scalars(
            select(Label.label).where(
                Label.note_id == note.id,
                Label.label.in_(valid_anchors),
            )
        ).all()
    )

    created = 0
    for anchor in valid_anchors:
        if anchor not in existing_labels:
            upsert_label(session, note.id, anchor)
            created += 1

    if created:
        session.flush()

    return created


def _upsert_note_citations(session: Session, note: Note, bibkeys: list[str]) -> int:
    """Upsert Citation rows from frontmatter `references:` list. Returns new count."""
    from workflow.db.models.notes import Citation
    from workflow.notes.linker_ops import upsert_citation

    existing = set(session.scalars(
        select(Citation.citationkey).where(
            Citation.note_id == note.id,
            Citation.citationkey.in_(bibkeys),
        )
    ).all())

    created = 0
    for key in bibkeys:
        if not isinstance(key, str) or not key.strip():
            continue
        if key not in existing:
            upsert_citation(session, note.id, key)
            created += 1

    if created:
        session.flush()
    return created


def _upsert_note_links(session: Session, note: Note, body: str) -> int:
    """Upsert Link rows for all wikilinks in body. Returns new link count."""
    created = 0
    for target_ref, anchor in _extract_wikilinks(body):
        # Match by zettel_id first (canonical), fall back to legacy reference column
        target_note = session.scalars(
            select(Note).where(Note.zettel_id == target_ref)
        ).first()
        if target_note is None:
            target_note = session.scalars(
                select(Note).where(Note.reference == target_ref)
            ).first()
        if target_note is None:
            continue

        label_name = anchor if (anchor and _ANCHOR_RE.match(anchor)) else "__note__"

        target_label = session.scalars(
            select(Label).where(
                Label.note_id == target_note.id,
                Label.label == label_name,
            )
        ).first()
        if target_label is None:
            upsert_label(session, target_note.id, label_name)
            session.flush()
            target_label = session.scalars(
                select(Label).where(
                    Label.note_id == target_note.id,
                    Label.label == label_name,
                )
            ).first()

        if target_label is None:
            continue

        if upsert_link(session, note.id, target_label.id):
            created += 1

    if created:
        session.flush()

    return created


def _upsert_note_edges(session: Session, note: Note, fm: dict) -> int:
    """Upsert NoteEdge rows from relations: frontmatter block. Returns new edge count."""
    entries = parse_relations_frontmatter(fm)
    if not entries:
        return 0

    created = 0
    for entry in entries:
        # Resolve target zettel_id → DB id if the note is already synced
        target_note = session.scalars(
            select(Note).where(Note.zettel_id == entry.target_zettel_id)
        ).first()
        target_id = target_note.id if target_note else None

        if upsert_note_edge(
            session,
            source_id=note.id,
            target_zettel_id=entry.target_zettel_id,
            edge_class=entry.edge_class,
            relation_type=entry.relation_type,
            target_id=target_id,
            weight=entry.weight,
            rationale=entry.rationale,
        ):
            created += 1

    if created:
        session.flush()
    return created


def _rebuild_note_edges(session: Session, note: Note, fm: dict) -> int:
    """Delete all existing NoteEdge rows for this source, then re-upsert from frontmatter.

    This implements the --rebuild-edges semantic: stale/renamed edges are dropped
    atomically per note before the current frontmatter is re-imported.
    Returns the count of edges created after rebuild.
    """
    from sqlalchemy import delete as _delete

    session.execute(_delete(NoteEdge).where(NoteEdge.source_id == note.id))
    session.flush()
    return _upsert_note_edges(session, note, fm)


def _sync_note_concepts(
    session: Session,
    note: "Note",
    fm: dict,
    *,
    strict: bool = False,
) -> tuple[int, list[dict]]:
    """Upsert NoteConcept rows from frontmatter ``concepts:`` list.

    Returns (rows_upserted, issues). Issues follow resolve_concepts format:
    ``{"severity": "warning"|"error", "message": str}``.
    """
    from workflow.concept.service import resolve_concepts

    codes = [c for c in (fm.get("concepts") or []) if isinstance(c, str) and c.strip()]
    if not codes:
        return 0, []

    found, issues = resolve_concepts(codes, session, strict=strict)
    upserted = 0
    for concept in found:
        if upsert_note_concept(session, note_id=note.id, concept_id=concept.id):
            upserted += 1

    if upserted:
        session.flush()

    return upserted, issues


def _drop_orphan_links(
    session: Session,
    scope_prefix: str,
    current_filenames: set[str],
) -> int:
    """Delete Link rows whose source Note file is no longer on disk. Returns count."""
    # Scope prefix must end with separator to avoid matching sibling directories
    prefix_with_sep = scope_prefix.rstrip(os.sep) + os.sep

    all_notes = session.scalars(
        select(Note).where(Note.filename.startswith(prefix_with_sep))
    ).all()

    orphan_ids = [n.id for n in all_notes if n.filename not in current_filenames]
    if not orphan_ids:
        return 0

    orphan_links = session.scalars(
        select(Link).where(Link.source_id.in_(orphan_ids))
    ).all()

    for lnk in orphan_links:
        session.delete(lnk)

    if orphan_links:
        session.flush()

    return len(orphan_links)


def _resolve_scan_root(vault_root: Path, project_filter: str | None) -> Path:
    """Resolve the scan root, validating project_filter containment."""
    vault_root_resolved = vault_root.resolve()
    if project_filter:
        scan_root = (vault_root / project_filter).resolve()
        if not scan_root.is_relative_to(vault_root_resolved):
            raise ValueError(
                f"project_filter escapes vault_root: {project_filter!r}"
            )
        return scan_root
    return vault_root_resolved


def _run_write_passes(
    session: Session,
    note_data: list,
    scope_prefix: str,
    current_filenames: set[str],
    strict_concepts: bool,
    rebuild_edges: bool,
    report: SyncReport,
    *,
    skip_orphan_drop: bool = False,
) -> None:
    """Run passes 2-5: links, orphan drop, edges, concepts (all write paths).

    ``skip_orphan_drop`` lets an explicit-file-list caller (``sync_note_files``)
    reuse this orchestration without the orphan-drop pass ever running — see
    that function's docstring for why deletion-by-absence must stay exclusive
    to directory-wide ``sync_vault``.
    """
    for note, body, _fm in note_data:
        report.links_created += _upsert_note_links(session, note, body)

    if not skip_orphan_drop:
        report.orphans_dropped += _drop_orphan_links(session, scope_prefix, current_filenames)

    _edge_fn = _rebuild_note_edges if rebuild_edges else _upsert_note_edges
    for note, _body, fm in note_data:
        report.edges_created += _edge_fn(session, note, fm)

    for note, _body, fm in note_data:
        created, issues = _sync_note_concepts(session, note, fm, strict=strict_concepts)
        report.concept_links_created += created
        report.concept_issues.extend(issues)


def sync_vault(
    vault_root: Path,
    session: Session,
    *,
    dry_run: bool = False,
    project_filter: str | None = None,
    strict_concepts: bool = False,
    rebuild_edges: bool = False,
) -> SyncReport:
    """Scan vault_root/**/*.md, parse frontmatter + wikilinks, upsert Note/Label/Link rows.

    File-as-truth, DB-as-index. Idempotent.
    """
    report = SyncReport()
    vault_root_resolved = vault_root.resolve()
    scan_root = _resolve_scan_root(vault_root, project_filter)
    scope_prefix = str(scan_root)

    md_paths = [
        p for p in scan_root.rglob("*.md")
        if p.resolve().is_relative_to(vault_root_resolved)
    ]
    current_filenames: set[str] = {str(p) for p in md_paths}

    # Pass 1: upsert Note + Label rows (or dry-run count)
    note_data: list[tuple[Note, str, dict]] = []

    for md_path in md_paths:
        parsed = _parse_md(md_path)
        if parsed is None:
            continue
        fm, body = parsed
        zettel_id = fm.get("id")
        if not zettel_id or not isinstance(zettel_id, str):
            continue
        anchors: list[str] = list(fm.get("anchors") or [])
        bibkeys: list[str] = [
            k for k in (fm.get("references") or [])
            if isinstance(k, str) and k.strip()
        ]
        if dry_run:
            report.notes_scanned += 1
            report.labels_registered += 1 + sum(1 for a in anchors if _ANCHOR_RE.match(a))
            report.citations_registered += len(bibkeys)
            report.edges_created += len(parse_relations_frontmatter(fm))
            continue
        note = _upsert_note_row(session, str(md_path), {**fm, "id": zettel_id})
        report.notes_scanned += 1
        report.labels_registered += _upsert_note_labels(session, note, anchors)
        report.citations_registered += _upsert_note_citations(session, note, bibkeys)
        note_data.append((note, body, fm))

    if not dry_run:
        _run_write_passes(
            session, note_data, scope_prefix, current_filenames,
            strict_concepts, rebuild_edges, report,
        )

    return report


def sync_note_files(
    paths: list[Path],
    session: Session,
    *,
    strict_concepts: bool = False,
    rebuild_edges: bool = False,
) -> SyncReport:
    """Sync an explicit list of .md files into DB (Note/Label/Link/Edge/Concept rows).

    This is the Pass-1 equivalent of ``sync_vault`` for an explicit file list —
    e.g. the files a lecture monolith was just split into (``lectures split
    --sync``) — instead of a directory-wide ``scan_root.rglob("*.md")``. Pass
    2-5 (links, edges, concepts) are shared with ``sync_vault`` via
    ``_run_write_passes``.

    Deliberately never drops orphan links: an explicit file-list sync only
    ever adds/updates rows for the given ``paths``. Running the orphan-drop
    pass here would delete Link rows for every note NOT in ``paths`` under
    whatever scope happened to be inferred — wrong for a partial subset, since
    "not in this call's file list" does not mean "deleted from disk".
    Deletion-by-absence stays exclusive to directory-wide ``sync_vault``,
    which owns the full current-filenames set for its scope.
    """
    report = SyncReport()
    note_data: list[tuple[Note, str, dict]] = []

    for md_path in paths:
        parsed = _parse_md(md_path)
        if parsed is None:
            continue
        fm, body = parsed
        zettel_id = fm.get("id")
        if not zettel_id or not isinstance(zettel_id, str):
            continue
        anchors: list[str] = list(fm.get("anchors") or [])
        bibkeys: list[str] = [
            k for k in (fm.get("references") or [])
            if isinstance(k, str) and k.strip()
        ]
        note = _upsert_note_row(session, str(md_path), {**fm, "id": zettel_id})
        report.notes_scanned += 1
        report.labels_registered += _upsert_note_labels(session, note, anchors)
        report.citations_registered += _upsert_note_citations(session, note, bibkeys)
        note_data.append((note, body, fm))

    _run_write_passes(
        session, note_data, "", set(),
        strict_concepts, rebuild_edges, report,
        skip_orphan_drop=True,
    )

    return report
