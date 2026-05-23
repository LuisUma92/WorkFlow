"""0008_rename_note_concept_tag_id — rename note_concept.tag_id → concept_id.

Fixes schema drift on live DBs where note_concept was first created by
Base.metadata.create_all() before the column was renamed in the ORM.
Migration 0005 used CREATE TABLE IF NOT EXISTS so it never repaired the
legacy column.  Table-swap recipe, idempotent on both legacy and fresh
schemas.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0008_rename_note_concept_tag_id"
description: str = "Rename note_concept.tag_id → concept_id to match ORM model."
base: str = "global"


def upgrade(connection: Connection) -> None:
    cols = {
        row[1]
        for row in connection.exec_driver_sql(
            "PRAGMA table_info(note_concept)"
        ).fetchall()
    }
    if "concept_id" in cols:
        return  # already migrated
    if "tag_id" not in cols:
        return  # no legacy column either (table absent or other schema)

    connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
    connection.exec_driver_sql(
        """
        CREATE TABLE note_concept_new (
            note_id    INTEGER NOT NULL REFERENCES note(id)    ON DELETE CASCADE,
            concept_id INTEGER NOT NULL REFERENCES concept(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, concept_id)
        )
        """
    )
    connection.exec_driver_sql(
        "INSERT INTO note_concept_new (note_id, concept_id) "
        "SELECT note_id, tag_id FROM note_concept"
    )
    connection.exec_driver_sql("DROP TABLE note_concept")
    connection.exec_driver_sql(
        "ALTER TABLE note_concept_new RENAME TO note_concept"
    )
    connection.exec_driver_sql("PRAGMA foreign_keys = ON")
