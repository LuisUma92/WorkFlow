"""0014_bib_promoted_columns — promote high-value biblatex fields to first-class columns.

Adds 11 columns to ``bib_entry`` (ADR-0019 A3):

  Subtitle/titleaddon family:
    subtitle, booksubtitle, mainsubtitle, titleaddon, booktitleaddon, maintitleaddon

  Origin family:
    origdate, origlocation, origpublisher

  Identifiers:
    pubmedid, urlraw

All steps are idempotent via ``PRAGMA table_info`` probes (same pattern as 0012).
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0014_bib_promoted_columns"
description: str = (
    "Promote subtitle/titleaddon family, origdate/origlocation/origpublisher, "
    "pubmedid/urlraw to first-class BibEntry columns — ADR-0019 A3."
)
base: str = "global"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _col_names(connection: Connection, table: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _table_exists(connection: Connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


# Column definitions: (column_name, sql_type)
# Subtitle/titleaddon family, origin family, identifier fields (ADR-0019 A3).
_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    # Subtitle / titleaddon family
    ("subtitle", "VARCHAR(500)"),
    ("titleaddon", "VARCHAR(500)"),
    ("booksubtitle", "VARCHAR(500)"),
    ("booktitleaddon", "VARCHAR(500)"),
    ("mainsubtitle", "VARCHAR(500)"),
    ("maintitleaddon", "VARCHAR(500)"),
    # Origin / reprint family
    ("origdate", "VARCHAR(50)"),
    ("origlocation", "VARCHAR(200)"),
    ("origpublisher", "VARCHAR(200)"),
    # Identifier fields
    ("pubmedid", "VARCHAR(50)"),
    ("urlraw", "TEXT"),
)


def _add_column_if_absent(
    connection: Connection,
    table: str,
    col_name: str,
    col_type: str,
    existing_cols: set[str],
) -> None:
    if col_name not in existing_cols:
        connection.exec_driver_sql(
            f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
        )


def upgrade(connection: Connection) -> None:
    """Apply migration 0014 — idempotent.

    Adds each new column to ``bib_entry`` only when it does not already exist.
    """
    if not _table_exists(connection, "bib_entry"):
        return

    bib_cols = _col_names(connection, "bib_entry")
    for col_name, col_type in _NEW_COLUMNS:
        _add_column_if_absent(connection, "bib_entry", col_name, col_type, bib_cols)
