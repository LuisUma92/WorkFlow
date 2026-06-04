"""0013_bib_extra_fields — create bib_extra_field overflow table (ADR-0019 A1).

Creates the EAV overflow table that stores any catalog-known biblatex field
without a first-class BibEntry column.  Idempotent: guarded by a table-existence
check (same pattern as 0012).

Schema:
  bib_extra_field(id PK, bib_entry_id FK→bib_entry.id, field VARCHAR(100),
                  value TEXT, UNIQUE(bib_entry_id, field))
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0013_bib_extra_fields"
description: str = (
    "Create bib_extra_field EAV overflow table for catalog-known biblatex fields "
    "without a first-class BibEntry column — ADR-0019 A1."
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
    """Apply migration 0013 — idempotent.

    Creates the ``bib_extra_field`` table only if it does not already exist.
    The UNIQUE constraint on ``(bib_entry_id, field)`` prevents duplicate rows.
    """
    if _table_exists(connection, "bib_extra_field"):
        return  # already applied — no-op

    connection.exec_driver_sql(
        """
        CREATE TABLE bib_extra_field (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            bib_entry_id  INTEGER NOT NULL
                              REFERENCES bib_entry(id) ON DELETE CASCADE,
            field         VARCHAR(100) NOT NULL,
            value         TEXT         NOT NULL,
            UNIQUE (bib_entry_id, field)
        )
        """
    )
