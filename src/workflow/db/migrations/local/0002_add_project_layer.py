"""0002_add_project_layer — ITEP-0011 P5: add project_note + prisma_decision tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0002_add_project_layer"
description: str = "Add project_note and prisma_decision tables (ITEP-0011 P5)."


def upgrade(connection: Connection) -> None:
    connection.execute(__import__("sqlalchemy").text("""
        CREATE TABLE IF NOT EXISTS project_note (
            id         INTEGER PRIMARY KEY,
            kind       TEXT    NOT NULL
                               CHECK (kind IN ('idea', 'hypothesis', 'connection')),
            body       TEXT    NOT NULL,
            global_note_ref TEXT,
            created_at DATETIME NOT NULL DEFAULT (datetime('now'))
        )
    """))
    connection.execute(__import__("sqlalchemy").text("""
        CREATE TABLE IF NOT EXISTS prisma_decision (
            id          INTEGER PRIMARY KEY,
            bibkey      TEXT    NOT NULL,
            decision    TEXT    NOT NULL
                                CHECK (decision IN ('included', 'excluded', 'uncertain')),
            rationale   TEXT,
            reviewer    TEXT,
            reviewed_at DATETIME,
            UNIQUE (bibkey)
        )
    """))
