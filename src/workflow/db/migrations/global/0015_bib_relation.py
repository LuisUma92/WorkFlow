"""0015_bib_relation — create bib_relation table (ADR-0019 A4).

Stores biblatex inter-entry relations (crossref/xref/xdata/related) as
(child, parent_bibkey, kind) rows.  ``parent_id`` is resolved to a bib_entry
when the target exists; ``parent_bibkey`` is always preserved so forward
references and missing targets stay lossless.  Idempotent: guarded by a
table-existence check (same pattern as 0013).

Schema:
  bib_relation(id PK, child_id FK→bib_entry.id, parent_bibkey VARCHAR(255),
               parent_id FK→bib_entry.id NULL, kind VARCHAR(20),
               UNIQUE(child_id, kind, parent_bibkey))
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0015_bib_relation"
description: str = (
    "Create bib_relation table for biblatex crossref/xref/xdata/related "
    "inter-entry relations — ADR-0019 A4."
)
base: str = "global"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_exists(connection: Connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade(connection: Connection) -> None:
    """Apply migration 0015 — idempotent.

    Creates the ``bib_relation`` table if absent (UNIQUE on
    ``(child_id, kind, parent_bibkey)`` makes re-import idempotent), then drops
    any pre-A4 overflow rows for the relation fields. Before A4 those fields
    were stored in ``bib_extra_field``; leaving them there would double-emit on
    export once the same entry also has ``bib_relation`` rows. Both steps are
    idempotent (the DELETE is a no-op on a clean DB).
    """
    if not _table_exists(connection, "bib_relation"):
        connection.exec_driver_sql(
            """
            CREATE TABLE bib_relation (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id       INTEGER NOT NULL
                                   REFERENCES bib_entry(id) ON DELETE CASCADE,
                parent_bibkey  VARCHAR(255) NOT NULL,
                parent_id      INTEGER
                                   REFERENCES bib_entry(id) ON DELETE SET NULL,
                kind           VARCHAR(20)  NOT NULL,
                UNIQUE (child_id, kind, parent_bibkey)
            )
            """
        )

    if _table_exists(connection, "bib_extra_field"):
        connection.exec_driver_sql(
            "DELETE FROM bib_extra_field "
            "WHERE field IN ('crossref', 'xref', 'xdata', 'related')"
        )
