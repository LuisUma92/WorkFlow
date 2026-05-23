"""0007_add_note_edges — create note_edge table (ITEP-0013 P2.1).

Forward-only migration creating the note_edge table for the Zettelkasten
relation graph.  Idempotent: skips CREATE TABLE if already present, uses
CREATE INDEX IF NOT EXISTS for all three indexes.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0007_add_note_edges"
description: str = "Create note_edge table for Zettelkasten relation graph (ITEP-0013)."
base: str = "global"


def upgrade(connection: Connection) -> None:
    tables = {
        row[0]
        for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "note_edge" not in tables:
        connection.exec_driver_sql(
            """
            CREATE TABLE note_edge (
                id              INTEGER PRIMARY KEY,
                source_id       INTEGER NOT NULL
                                    REFERENCES note(id) ON DELETE CASCADE,
                target_id       INTEGER
                                    REFERENCES note(id) ON DELETE SET NULL,
                target_zettel_id VARCHAR(21) NOT NULL,
                edge_class      VARCHAR(16) NOT NULL,
                relation_type   VARCHAR(24) NOT NULL,
                weight          REAL NOT NULL DEFAULT 1.0,
                rationale       TEXT,
                created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ck_note_edge_class_valid
                    CHECK (edge_class IN ('structural', 'associative')),
                CONSTRAINT ck_note_edge_relation_type_valid
                    CHECK (relation_type IN (
                        'continuation', 'refines', 'branches', 'synthesis', 'rebuttal',
                        'supports', 'contradicts', 'expands', 'see_also'
                    )),
                CONSTRAINT uq_note_edge_src_tgt_rel
                    UNIQUE (source_id, target_zettel_id, relation_type)
            )
            """
        )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_note_edge_source "
        "ON note_edge(source_id, edge_class, relation_type)"
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_note_edge_target "
        "ON note_edge(target_id, edge_class, relation_type)"
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_note_edge_unresolved "
        "ON note_edge(target_zettel_id)"
    )
