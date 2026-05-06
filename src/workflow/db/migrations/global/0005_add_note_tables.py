"""0005_add_note_tables — create note tables on GlobalBase.

Forward-only migration that materializes the note layer (``note``,
``citation``, ``label``, ``link``, ``tag``, ``note_tag``, ``concept``,
``note_concept``) on the global database for ITEP-0011 vault unification.

P1 used ``GlobalBase.metadata.create_all`` to ship these tables on dev DBs.
This migration formalizes them under the ITEP-0010 forward-only flow so
clean global DBs created after P1 still pick up the schema.

Uses ``CREATE TABLE IF NOT EXISTS`` so it composes safely with DBs already
built by ``metadata.create_all``.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0005_add_note_tables"
description: str = "Create note layer tables on GlobalBase (ITEP-0011 P2 / OQ6)."
base: str = "global"


_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS note (
        id INTEGER PRIMARY KEY,
        filename VARCHAR NOT NULL UNIQUE,
        reference VARCHAR NOT NULL UNIQUE,
        last_build_date_html DATETIME,
        last_build_date_pdf DATETIME,
        last_edit_date DATETIME,
        created DATETIME,
        title VARCHAR(200),
        note_type VARCHAR(20),
        source_format VARCHAR(5),
        zettel_id VARCHAR(100) UNIQUE,
        CONSTRAINT ck_note_type_valid CHECK (
            note_type IN ('permanent', 'literature', 'fleeting')
            OR note_type IS NULL
        ),
        CONSTRAINT ck_source_format_valid CHECK (
            source_format IN ('md', 'tex') OR source_format IS NULL
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS citation (
        id INTEGER PRIMARY KEY,
        note_id INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE,
        citationkey VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS label (
        id INTEGER PRIMARY KEY,
        note_id INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE,
        label VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS link (
        id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE,
        target_id INTEGER NOT NULL REFERENCES label(id) ON DELETE CASCADE,
        CONSTRAINT uq_link_source_target UNIQUE (source_id, target_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tag (
        id INTEGER PRIMARY KEY,
        name VARCHAR NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS note_tag (
        note_id INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE,
        tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
        PRIMARY KEY (note_id, tag_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS concept (
        id INTEGER PRIMARY KEY,
        main_topic_id INTEGER NOT NULL REFERENCES main_topic(id) ON DELETE RESTRICT,
        code VARCHAR(32) NOT NULL UNIQUE,
        label VARCHAR(255) NOT NULL,
        description VARCHAR,
        parent_id INTEGER REFERENCES concept(id) ON DELETE SET NULL,
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS note_concept (
        note_id INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE,
        concept_id INTEGER NOT NULL REFERENCES concept(id) ON DELETE CASCADE,
        PRIMARY KEY (note_id, concept_id)
    )
    """,
)


def upgrade(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)
