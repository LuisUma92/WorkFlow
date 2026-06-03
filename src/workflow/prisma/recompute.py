"""Calculated-bibkey recompute service (Phase 3).

Provides a pure-ish service layer for ``workflow prisma bib recompute-keys``.
All DB mutation is isolated in :func:`apply_recompute`; the planner
(:func:`compute_recompute_plan`) is side-effect-free.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, selectinload

from workflow.bibliography.bibkey import calculate_bibkey
from workflow.db.models.bibliography import BibAuthor, BibEntry
from workflow.prisma.importer import disambiguate_bibkey

__all__ = [
    "BibkeyChange",
    "backup_database",
    "apply_recompute",
    "compute_recompute_plan",
]


@dataclass(frozen=True)
class BibkeyChange:
    """Describes a single bibkey change (old → new) for one BibEntry."""

    entry_id: int
    title: str | None
    old_bibkey: str | None
    new_bibkey: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _surname_for_entry(entry: BibEntry) -> tuple[str | None, str | None]:
    """Return (last_name, name_prefix) for the first author of *entry*.

    Selection priority:
    1. The ``BibAuthor`` with ``first_author == True``.
    2. The first element of ``author_links`` if none is flagged.
    3. ``(None, None)`` when there are no author links at all.
    """
    links: list[BibAuthor] = entry.author_links
    if not links:
        return (None, None)

    flagged = next((lnk for lnk in links if lnk.first_author), None)
    chosen = flagged if flagged is not None else links[0]
    author = chosen.author
    return (author.last_name or None, author.name_prefix)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_recompute_plan(
    session: Session,
    *,
    fill_missing_only: bool,
) -> list[BibkeyChange]:
    """Build the list of bibkey changes without mutating the database.

    Parameters
    ----------
    session:
        Active SQLAlchemy session (read-only usage; no flush/commit).
    fill_missing_only:
        ``True``  → Default mode. Only entries with a NULL or empty bibkey
                    are assigned a calculated key.  Existing non-empty keys
                    are kept and seeded into *taken* so new keys cannot
                    collide with them.
        ``False`` → ``--all`` mode. Every entry's bibkey is recalculated.
                    Existing keys are not seeded; the plan reassigns all.

    Returns
    -------
    list[BibkeyChange]
        Changes that would be applied (entries where new key ≠ old key).

    Idempotency contract
    --------------------
    ``fill_missing_only=True`` is idempotent by construction: after a first
    run every previously-NULL key is non-empty, so those entries are excluded
    on re-run and the result is an empty changeset.

    ``fill_missing_only=False`` (``--all``) idempotency depends on the
    deterministic ``ORDER BY BibEntry.id`` traversal below — collision-suffix
    assignments (a, b, …) are stable only when the traversal order is fixed.
    Keep the ORDER BY clause to preserve this guarantee.  Caveat: inserting
    new entries that collide with existing ones between two ``--all`` runs can
    shift suffix assignments for later entries in that collision group.
    """
    # ORDER BY BibEntry.id is load-bearing for idempotency — do not remove.
    stmt = (
        select(BibEntry)
        .options(
            selectinload(BibEntry.author_links).selectinload(BibAuthor.author)
        )
        .order_by(BibEntry.id)
    )
    all_entries: list[BibEntry] = list(session.scalars(stmt))

    taken: set[str] = set()

    if fill_missing_only:
        # Seed taken with ALL existing non-empty keys (they are immutable).
        for entry in all_entries:
            if entry.bibkey and entry.bibkey.strip():
                taken.add(entry.bibkey)

    # Entries to recompute.
    targets = (
        [e for e in all_entries if not (e.bibkey and e.bibkey.strip())]
        if fill_missing_only
        else all_entries
    )

    changes: list[BibkeyChange] = []

    for entry in targets:
        last_name, name_prefix = _surname_for_entry(entry)
        candidate = calculate_bibkey(
            surname=last_name,
            year=entry.year,
            volume=entry.volume,
            edition=entry.edition,
            entry_type=entry.entry_type,
            name_prefix=name_prefix,
        )
        new_key = disambiguate_bibkey(candidate, taken)
        taken.add(new_key)

        old_key = entry.bibkey or None
        if new_key != old_key:
            changes.append(
                BibkeyChange(
                    entry_id=entry.id,
                    title=entry.title,
                    old_bibkey=old_key,
                    new_bibkey=new_key,
                )
            )

    return changes


def backup_database(engine: Engine) -> Path | None:
    """Copy the SQLite database file to a timestamped ``.bak-YYYYMMDDHHMMSS`` path.

    Parameters
    ----------
    engine:
        SQLAlchemy engine whose ``url.database`` points to the DB file.

    Returns
    -------
    Path | None
        Absolute path to the backup file, or ``None`` for in-memory / missing
        databases.

    Raises
    ------
    OSError
        Propagated directly from ``shutil.copy2`` if the copy fails.  Callers
        should catch this and abort before making any DB mutations.
    """
    db_path_str: str | None = engine.url.database
    if not db_path_str or db_path_str in (":memory:", ""):
        return None

    db_path = Path(db_path_str)
    if not db_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak-{timestamp}")
    shutil.copy2(db_path, backup_path)  # OSError propagates to caller
    return backup_path


def apply_recompute(session: Session, changes: list[BibkeyChange]) -> None:
    """Apply *changes* to BibEntry rows.  Caller is responsible for commit.

    Parameters
    ----------
    session:
        Active SQLAlchemy session; must have the same engine used to build
        *changes*.
    changes:
        List returned by :func:`compute_recompute_plan`.
    """
    if not changes:
        return

    ids = [c.entry_id for c in changes]
    entries_by_id: dict[int, BibEntry] = {
        e.id: e
        for e in session.scalars(select(BibEntry).where(BibEntry.id.in_(ids)))
    }

    for change in changes:
        entry = entries_by_id.get(change.entry_id)
        if entry is not None:
            entry.bibkey = change.new_bibkey

    session.flush()
