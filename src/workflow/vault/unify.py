"""ITEP-0011 P2 — vault unification logic.

Migrates a per-project ``slipbox.db`` (LocalBase note layer, pre-P1) into
the unified GlobalBase note layer, moves the project's ``.md`` notes into
``<vault_root>/notes/<note_type>/``, and writes a ``.vault_pointer`` marker.

The reader uses raw ``sqlite3`` against the legacy slipbox so this module
does not depend on the (now-removed) LocalBase note ORM.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from workflow.db.models.notes import (
    Citation,
    Label,
    Link,
    Note,
    NoteTag,
    Tag,
)

RenameStrategy = Literal["project-prefix", "abort", "manual"]
NOTE_TYPES = ("permanent", "literature", "fleeting")
DEFAULT_NOTE_TYPE = "permanent"
VAULT_POINTER_FILE = ".vault_pointer"
LEGACY_SLIPBOX = "slipbox.db"


@dataclass
class UnifyReport:
    project_name: str
    dry_run: bool
    notes_migrated: int = 0
    citations_migrated: int = 0
    labels_migrated: int = 0
    links_migrated: int = 0
    tags_migrated: int = 0
    note_tags_migrated: int = 0
    files_moved: int = 0
    collisions: list[str] = field(default_factory=list)
    orphans: list[int] = field(default_factory=list)
    backup_path: Path | None = None
    note_id_remap: dict[int, int] = field(default_factory=dict)
    label_id_remap: dict[int, int] = field(default_factory=dict)
    tag_id_remap: dict[int, int] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: str | None = None


def unify(
    project_root: Path,
    vault_root: Path,
    *,
    backup_dir: Path,
    global_session: Session,
    rename_strategy: RenameStrategy = "abort",
    dry_run: bool = True,
) -> UnifyReport:
    """Move a project's slipbox notes + .md files into the global vault.

    Returns a report. When ``dry_run`` is True no DB writes, file moves,
    backups, or marker writes occur.

    Raises:
        FileNotFoundError: project_root or vault_root missing.
        ValueError: collision detected with rename_strategy='abort'.
    """
    project_root = Path(project_root).resolve()
    vault_root = Path(vault_root).resolve()
    backup_dir = Path(backup_dir).resolve()

    if not project_root.is_dir():
        raise FileNotFoundError(f"project_root not found: {project_root}")
    if not vault_root.is_dir():
        raise FileNotFoundError(f"vault_root not found: {vault_root}")

    project_name = project_root.name
    report = UnifyReport(project_name=project_name, dry_run=dry_run)

    pointer = project_root / VAULT_POINTER_FILE
    if pointer.exists():
        report.skipped = True
        report.skip_reason = "already unified (.vault_pointer present)"
        return report

    slipbox = project_root / LEGACY_SLIPBOX
    if not slipbox.exists():
        report.skipped = True
        report.skip_reason = f"no {LEGACY_SLIPBOX} in project"
        return report

    legacy = _read_slipbox(slipbox)

    if not legacy.notes:
        if not dry_run:
            _write_pointer(pointer, vault_root)
        return report

    existing_refs = {
        ref for (ref,) in global_session.query(Note.reference).all()
    }
    existing_zids = {
        z for (z,) in global_session.query(Note.zettel_id).all() if z is not None
    }

    rename_map: dict[int, tuple[str, str | None]] = {}
    for n in legacy.notes:
        new_ref = n["reference"]
        new_zid = n["zettel_id"]
        collided = new_ref in existing_refs or (
            new_zid is not None and new_zid in existing_zids
        )
        if collided:
            if rename_strategy == "abort":
                report.collisions.append(new_ref)
            elif rename_strategy == "project-prefix":
                new_ref = f"{project_name}:{new_ref}"
                if new_zid is not None:
                    new_zid = f"{project_name}:{new_zid}"
                rename_map[n["id"]] = (new_ref, new_zid)
                report.collisions.append(n["reference"])
            else:  # manual
                report.collisions.append(new_ref)
        else:
            rename_map[n["id"]] = (new_ref, new_zid)

    if rename_strategy == "abort" and report.collisions:
        raise ValueError(
            f"Reference collisions ({len(report.collisions)}); "
            f"first: {report.collisions[0]!r}. Use --rename-strategy."
        )

    if not dry_run:
        report.backup_path = _snapshot(slipbox, backup_dir, project_name)

    notes_to_migrate = [n for n in legacy.notes if n["id"] in rename_map]

    new_notes: dict[int, Note] = {}
    for n in notes_to_migrate:
        new_ref, new_zid = rename_map[n["id"]]
        nt = n["note_type"] if n["note_type"] in NOTE_TYPES else None
        note = Note(
            filename=_prefix(project_name, n["filename"], existing_refs),
            reference=new_ref,
            last_build_date_html=n["last_build_date_html"],
            last_build_date_pdf=n["last_build_date_pdf"],
            last_edit_date=n["last_edit_date"],
            created=n["created"],
            title=n["title"],
            note_type=nt,
            source_format=n["source_format"],
            zettel_id=new_zid,
        )
        new_notes[n["id"]] = note

    if not dry_run:
        global_session.add_all(new_notes.values())
        global_session.flush()
    for old_id, note in new_notes.items():
        report.note_id_remap[old_id] = note.id if note.id is not None else -1
    report.notes_migrated = len(new_notes)

    new_labels: dict[int, Label] = {}
    for lab in legacy.labels:
        if lab["note_id"] not in new_notes:
            continue
        new_lab = Label(
            note_id=new_notes[lab["note_id"]].id if not dry_run else 0,
            label=lab["label"],
        )
        new_labels[lab["id"]] = new_lab

    if not dry_run:
        global_session.add_all(new_labels.values())
        global_session.flush()
    for old_id, lab in new_labels.items():
        report.label_id_remap[old_id] = lab.id if lab.id is not None else -1
    report.labels_migrated = len(new_labels)

    for c in legacy.citations:
        if c["note_id"] not in new_notes:
            continue
        if not dry_run:
            global_session.add(
                Citation(
                    note_id=new_notes[c["note_id"]].id,
                    citationkey=c["citationkey"],
                )
            )
        report.citations_migrated += 1

    new_tag_by_name: dict[str, Tag] = {}
    for t in legacy.tags:
        existing = (
            global_session.query(Tag).filter_by(name=t["name"]).one_or_none()
            if not dry_run
            else None
        )
        if existing is not None:
            report.tag_id_remap[t["id"]] = existing.id
            new_tag_by_name[t["name"]] = existing
        else:
            tag = Tag(name=t["name"])
            new_tag_by_name[t["name"]] = tag
            if not dry_run:
                global_session.add(tag)
                global_session.flush()
                report.tag_id_remap[t["id"]] = tag.id
            report.tags_migrated += 1

    legacy_tag_name = {t["id"]: t["name"] for t in legacy.tags}
    for nt_row in legacy.note_tags:
        if nt_row["note_id"] not in new_notes:
            continue
        tag_name = legacy_tag_name.get(nt_row["tag_id"])
        if tag_name is None:
            continue
        tag = new_tag_by_name.get(tag_name)
        if tag is None:
            continue
        if not dry_run:
            global_session.add(
                NoteTag(
                    note_id=new_notes[nt_row["note_id"]].id,
                    tag_id=tag.id,
                )
            )
        report.note_tags_migrated += 1

    for ln in legacy.links:
        if ln["source_id"] not in new_notes:
            continue
        if ln["target_id"] not in new_labels:
            report.orphans.append(ln["id"])
            continue
        if not dry_run:
            global_session.add(
                Link(
                    source_id=new_notes[ln["source_id"]].id,
                    target_id=new_labels[ln["target_id"]].id,
                )
            )
        report.links_migrated += 1

    report.files_moved = _move_md_files(
        project_root, vault_root, new_notes, dry_run=dry_run
    )

    if not dry_run:
        _write_pointer(pointer, vault_root)

    if not dry_run and report.notes_migrated != len(notes_to_migrate):
        raise RuntimeError(
            f"Count mismatch: migrated={report.notes_migrated} "
            f"expected={len(notes_to_migrate)}"
        )

    return report


@dataclass
class _LegacyData:
    notes: list[dict]
    citations: list[dict]
    labels: list[dict]
    links: list[dict]
    tags: list[dict]
    note_tags: list[dict]


def _read_slipbox(slipbox: Path) -> _LegacyData:
    conn = sqlite3.connect(str(slipbox))
    conn.row_factory = sqlite3.Row
    try:
        notes = [dict(r) for r in conn.execute("SELECT * FROM note")]
        citations = [dict(r) for r in conn.execute("SELECT * FROM citation")]
        labels = [dict(r) for r in conn.execute("SELECT * FROM label")]
        links = [dict(r) for r in conn.execute("SELECT * FROM link")]
        tags = [dict(r) for r in conn.execute("SELECT * FROM tag")]
        note_tags = [dict(r) for r in conn.execute("SELECT * FROM note_tag")]
    finally:
        conn.close()

    for table in (notes,):
        for row in table:
            for k in ("last_build_date_html", "last_build_date_pdf",
                      "last_edit_date", "created"):
                v = row.get(k)
                if isinstance(v, str):
                    try:
                        row[k] = datetime.fromisoformat(v)
                    except ValueError:
                        row[k] = None

    return _LegacyData(
        notes=notes,
        citations=citations,
        labels=labels,
        links=links,
        tags=tags,
        note_tags=note_tags,
    )


def _snapshot(slipbox: Path, backup_dir: Path, project_name: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = backup_dir / f"{project_name}-{ts}.db"
    shutil.copy2(slipbox, dest)
    return dest


def _write_pointer(pointer: Path, vault_root: Path) -> None:
    pointer.write_text(f"vault_root: {vault_root}\n", encoding="utf-8")


def _prefix(project_name: str, value: str, existing: set[str]) -> str:
    """Filename uniqueness shim — prepend project name on collision."""
    if value not in existing:
        return value
    return f"{project_name}/{value}"


def _move_md_files(
    project_root: Path,
    vault_root: Path,
    new_notes: dict[int, Note],
    *,
    dry_run: bool,
) -> int:
    notes_dir = project_root / "notes"
    if not notes_dir.is_dir():
        return 0
    moved = 0
    by_filename: dict[str, str] = {}
    for note in new_notes.values():
        nt = note.note_type if note.note_type in NOTE_TYPES else DEFAULT_NOTE_TYPE
        by_filename[note.filename.split("/")[-1]] = nt
    for md in notes_dir.rglob("*.md"):
        nt = by_filename.get(md.stem) or by_filename.get(md.name) or DEFAULT_NOTE_TYPE
        target_dir = vault_root / "notes" / nt
        target = target_dir / md.name
        if dry_run:
            moved += 1
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target_dir / f"{project_root.name}-{md.name}"
        shutil.move(str(md), str(target))
        moved += 1
    return moved
