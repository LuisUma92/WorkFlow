"""0006_note_main_topic_id — add note.main_topic_id (Phase B).

Forward-only migration adding a nullable ``main_topic_id`` column to
``note`` with a real ``REFERENCES main_topic(id) ON DELETE SET NULL``.
After ITEP-0011 P1+P2 the note table lives on GlobalBase alongside
``main_topic``, so the FK is enforceable by SQLite (with
``PRAGMA foreign_keys=ON``).

Idempotent: PRAGMA table_info guard skips when column exists.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0006_note_main_topic_id"
description: str = "Add nullable note.main_topic_id FK to main_topic.id."
base: str = "global"


def upgrade(connection: Connection) -> None:
    rows = connection.exec_driver_sql("PRAGMA table_info(note)").fetchall()
    cols = {r[1] for r in rows}
    if "main_topic_id" not in cols:
        connection.exec_driver_sql(
            "ALTER TABLE note ADD COLUMN main_topic_id INTEGER "
            "REFERENCES main_topic(id) ON DELETE SET NULL"
        )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_note_main_topic_id "
        "ON note(main_topic_id)"
    )
