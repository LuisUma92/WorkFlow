"""0012_bib_dialect_columns — add biblatex dialect columns (ADR-0019 P2.3).

Schema additions:
  bib_entry: date VARCHAR(50), chapter VARCHAR(200), type VARCHAR(100)
  author:    name_prefix VARCHAR(80), name_suffix VARCHAR(80)

Backfill:
  bib_entry.date = year  (or 'year-month' when month is present)
  for rows where date IS NULL AND year IS NOT NULL.

All steps are idempotent via PRAGMA table_info probes.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0012_bib_dialect_columns"
description: str = (
    "Add BibLaTeX dialect columns to bib_entry (date, chapter, type) "
    "and author (name_prefix, name_suffix) — ADR-0019 P2.3."
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


def upgrade(connection: Connection) -> None:
    """Apply migration 0012 — idempotent.

    Steps:
    1. Add date/chapter/type to bib_entry (skip each if column already exists).
    2. Add name_prefix/name_suffix to author (skip if already exist).
    3. Backfill bib_entry.date from year/month for pre-existing rows.
    """
    # ------------------------------------------------------------------
    # Step 1: bib_entry new columns
    # ------------------------------------------------------------------
    if _table_exists(connection, "bib_entry"):
        bib_cols = _col_names(connection, "bib_entry")
        if "date" not in bib_cols:
            connection.exec_driver_sql(
                "ALTER TABLE bib_entry ADD COLUMN date VARCHAR(50)"
            )
        if "chapter" not in bib_cols:
            connection.exec_driver_sql(
                "ALTER TABLE bib_entry ADD COLUMN chapter VARCHAR(200)"
            )
        if "type" not in bib_cols:
            connection.exec_driver_sql(
                "ALTER TABLE bib_entry ADD COLUMN type VARCHAR(100)"
            )

    # ------------------------------------------------------------------
    # Step 2: author new columns
    # ------------------------------------------------------------------
    if _table_exists(connection, "author"):
        author_cols = _col_names(connection, "author")
        if "name_prefix" not in author_cols:
            connection.exec_driver_sql(
                "ALTER TABLE author ADD COLUMN name_prefix VARCHAR(80)"
            )
        if "name_suffix" not in author_cols:
            connection.exec_driver_sql(
                "ALTER TABLE author ADD COLUMN name_suffix VARCHAR(80)"
            )

    # ------------------------------------------------------------------
    # Step 3: backfill bib_entry.date for existing rows
    #
    # Two UPDATE statements are used so that the month component is only
    # appended when it is numeric (1–2 digit string), producing a valid
    # ISO / biblatex date literal ("YYYY-MM").  Non-numeric month values
    # (e.g. "Jan", "February") are excluded from the month-bearing UPDATE
    # and receive a year-only literal instead via the second UPDATE.
    #
    # Both updates are guarded by ``date IS NULL`` — they are therefore safe
    # no-ops on re-run: if the migration has already been applied the rows
    # already have a non-NULL date and neither statement touches them again.
    # ------------------------------------------------------------------
    if _table_exists(connection, "bib_entry"):
        # 3a: rows where month is present AND numeric → "YYYY-MM"
        connection.exec_driver_sql(
            """
            UPDATE bib_entry
               SET date = CAST(year AS TEXT) || '-' || month
             WHERE date IS NULL
               AND year IS NOT NULL
               AND month IS NOT NULL
               AND month != ''
               AND month GLOB '[0-9]*'
               AND CAST(month AS INTEGER) BETWEEN 1 AND 12
            """
        )
        # 3b: rows with no month, or a non-numeric month → "YYYY"
        connection.exec_driver_sql(
            """
            UPDATE bib_entry
               SET date = CAST(year AS TEXT)
             WHERE date IS NULL
               AND year IS NOT NULL
            """
        )
