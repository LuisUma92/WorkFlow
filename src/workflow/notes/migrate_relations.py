"""`workflow notes migrate-relations` engine (ITEP-0013 F5).

Rewrites legacy nested ``relations:`` frontmatter blocks into the canonical
flat schema (9 keys, Obsidian Properties compatible — see
``workflow.notes.edges``). This is a filesystem-only, DB-free operation:
the flat/nested parser dispatch already lives in
``parse_relations_frontmatter`` and is used unmodified by ``sync.py``; this
command only rewrites the .md files on disk so the canonical schema is
present everywhere.

Per-note atomicity: a note is either fully rewritten or left untouched.
One bad note (corrupted ``relations: "<str>"``, the signature of a note
Obsidian Properties has already destroyed) never aborts the run — it is
collected as a failure and the run exits 1 at the end, while every other
note still migrates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from workflow.notes.discovery import parse_frontmatter, walk_note_files
from workflow.notes.edges import (
    RelationEntry,
    _parse_nested,
    has_legacy_relations,
    relations_to_flat_fm,
)

__all__ = ["DroppedField", "MigrationFailure", "MigrationReport", "migrate_relations"]


@dataclass(frozen=True)
class DroppedField:
    """A weight/rationale value silently dropped by the flat schema."""

    source: str
    target: str
    field: str  # "weight" | "note"
    value: object


@dataclass(frozen=True)
class MigrationFailure:
    """A note that could not be migrated."""

    path: str
    reason: str


@dataclass
class MigrationReport:
    scanned: int = 0
    migrated: list[str] = field(default_factory=list)
    skipped: int = 0
    failed: list[MigrationFailure] = field(default_factory=list)
    dropped: list[DroppedField] = field(default_factory=list)


_CORRUPTED_REASON = (
    "relations: is a plain string — this note's graph was already "
    "collapsed by Obsidian Properties and cannot be recovered by the "
    "parser. Restore this file from git history before re-running."
)


def _rebuild_raw_dict(raw: dict, flat: dict[str, list[str]]) -> dict:
    """Return a new raw frontmatter dict with `relations:` replaced in place.

    Preserves surrounding key order (minimal git diff): the flat keys are
    spliced in at the position the old `relations:` key occupied.
    """
    new_raw: dict = {}
    for key, value in raw.items():
        if key == "relations":
            for flat_key, flat_val in flat.items():
                new_raw[flat_key] = flat_val
            continue
        new_raw[key] = value
    return new_raw


def _collect_dropped(source_id: str, entries: list[RelationEntry]) -> list[DroppedField]:
    dropped: list[DroppedField] = []
    for entry in entries:
        if entry.weight != 1.0:
            dropped.append(
                DroppedField(
                    source=source_id,
                    target=entry.target_zettel_id,
                    field="weight",
                    value=entry.weight,
                )
            )
        if entry.rationale is not None:
            dropped.append(
                DroppedField(
                    source=source_id,
                    target=entry.target_zettel_id,
                    field="note",
                    value=entry.rationale,
                )
            )
    return dropped


def migrate_relations(
    vault_root: Path,
    *,
    dry_run: bool = False,
) -> MigrationReport:
    """Scan *vault_root* and rewrite legacy nested ``relations:`` to flat.

    Args:
        vault_root: Root directory to scan (recursive, reuses
            ``walk_note_files`` — same directory-skip rules as ``notes sync``).
        dry_run: If True, computes the full plan (migrated/skipped/failed/
            dropped) but writes nothing to disk.

    Returns:
        MigrationReport. Callers decide the process exit code (1 if
        ``report.failed`` is non-empty).
    """
    report = MigrationReport()

    for path in walk_note_files(vault_root):
        report.scanned += 1

        try:
            fm, body = parse_frontmatter(path)
        except ValueError as exc:
            report.failed.append(MigrationFailure(path=str(path), reason=str(exc)))
            continue

        if not has_legacy_relations(fm):
            report.skipped += 1
            continue

        relations = fm.get("relations")
        if isinstance(relations, str):
            report.failed.append(
                MigrationFailure(path=str(path), reason=_CORRUPTED_REASON)
            )
            continue

        source_id = fm.get("id")
        source_label = source_id if isinstance(source_id, str) else str(path)

        entries = _parse_nested(fm)
        flat = relations_to_flat_fm(entries)
        dropped = _collect_dropped(source_label, entries)
        report.dropped.extend(dropped)

        new_raw = _rebuild_raw_dict(fm, flat)

        if not dry_run:
            fm_yaml = yaml.safe_dump(new_raw, allow_unicode=True, sort_keys=False)
            path.write_text(f"---\n{fm_yaml}---\n{body}", encoding="utf-8")

        report.migrated.append(str(path))

    return report
