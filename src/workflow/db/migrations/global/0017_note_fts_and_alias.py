"""0017_note_fts_and_alias — vault full-text search (ADR-0021) + note_alias (ITEP-0015).

Adds two additive, forward-only schema pieces:

1. ``note_fts`` — an FTS5 virtual table indexing ``title``, ``aliases``,
   ``body`` per note, with ``tokenize='unicode61 remove_diacritics 2'`` so
   Spanish accents/ñ are query-insensitive (``teoria`` matches ``teoría``).

   **Deviation from ADR-0021's literal wording, documented here on purpose**:
   the ADR's Resolved design questions section locks "external-content"
   (``content='note', content_rowid='id'``). True SQLite FTS5 external-content
   mode requires the backing content table to actually own the indexed
   columns (``note.title``, ``note.aliases``, ``note.body``) — FTS5's special
   ``INSERT INTO note_fts(note_fts) VALUES('rebuild')`` command works by
   running ``INSERT INTO note_fts(rowid, <cols>) SELECT id, <cols> FROM note``
   under the hood, which fails outright if those columns don't exist on
   ``note``. ``Note`` has no ``aliases``/``body`` columns today (ADR-0010:
   ``.md`` files are body's truth, not the DB), and adding them would create
   a second body authority — exactly what ADR-0021's own Context section
   argues against.

   The pragmatic implementation of the ADR's *intent* (derived, rebuildable,
   rowid pinned to ``Note.id``, no ripgrep/no external service) is therefore
   a **standalone FTS5 table whose rowid is explicitly set to ``Note.id`` on
   every upsert** (``workflow.notes.sync``'s FTS pass does
   ``INSERT INTO note_fts(rowid, title, aliases, body) VALUES (?, ?, ?, ?)``
   followed by a delete-then-insert, never relying on FTS5's own
   external-content rebuild machinery). This keeps every property ADR-0021
   actually cares about — rebuildable from disk, rowid=Note.id, no duplicated
   authority in ``Note`` itself, delete+reinsert idempotent — without the
   literal ``content=`` SQLite option, which the schema cannot honor.

2. ``note_alias`` — ``note_id`` FK + unique ``alias`` text, per ITEP-0015 §F.
   Folded into this same migration per ADR-0021's Change Log (2026-07-05):
   "note_alias migration -> folded into this ADR's migration."

Both are pure additions; nothing existing is altered. Idempotent via
``IF NOT EXISTS`` on both DDL statements — matches the guard style of
0016 (checked-existence before mutating), just expressed through SQLite's
own idempotent DDL forms since these are CREATE, not UPDATE, statements.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0017_note_fts_and_alias"
description: str = (
    "Add note_fts FTS5 virtual table (title/aliases/body, unicode61 "
    "remove_diacritics=2 tokenizer, rowid=Note.id, standalone-storage "
    "deviation from ADR-0021's literal external-content wording — see "
    "module docstring) and note_alias table (ITEP-0015 SS F, folded in "
    "per ADR-0021 change log)."
)
base: str = "global"


def _table_exists(connection: Connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def upgrade(connection: Connection) -> None:
    if not _table_exists(connection, "note_fts"):
        connection.exec_driver_sql(
            "CREATE VIRTUAL TABLE note_fts USING fts5("
            "title, aliases, body, "
            "tokenize='unicode61 remove_diacritics 2'"
            ")"
        )

    if not _table_exists(connection, "note_alias"):
        connection.exec_driver_sql(
            "CREATE TABLE note_alias ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "note_id INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE, "
            "alias TEXT NOT NULL UNIQUE"
            ")"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_note_alias_note_id ON note_alias(note_id)"
        )
