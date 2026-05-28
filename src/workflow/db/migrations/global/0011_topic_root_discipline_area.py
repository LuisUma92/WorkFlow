"""0011_topic_root_discipline_area — Re-root Topic at DisciplineArea + add MainTopicSyllabus.

Changes:
  1. Rebuilds the ``topic`` table:
       - Drops ``main_topic_id`` FK column.
       - Adds ``discipline_area_id`` NOT NULL FK → discipline_area(id) ON DELETE RESTRICT.
       - Adds UNIQUE constraint ``(discipline_area_id, serial_number)``.
  2. Creates ``main_topic_syllabus`` join table:
       - Composite PK ``(main_topic_id, topic_id)``.
       - Both FKs ON DELETE CASCADE.
       - ``week_no INTEGER NULL``, ``order_no INTEGER NOT NULL``.
       - Index ``ix_main_topic_syllabus_topic`` on ``topic_id``.

Live DB has 0 topic rows — migration is structural-only; no data migration needed.
All steps are idempotent via ``PRAGMA table_info`` / ``sqlite_master`` probes.

ADR refs: ITEP-0002, ITEP-0008.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0011_topic_root_discipline_area"
description: str = (
    "Re-root Topic at DisciplineArea + add MainTopicSyllabus join (ADR ITEP-0002 + ITEP-0008)"
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
    """Apply migration 0011.

    Step 1 — Rebuild ``topic``:
      Create ``topic_new`` with new schema, skip INSERT (0 rows guaranteed),
      drop old table, rename new to ``topic``.

    Step 2 — Create ``main_topic_syllabus`` with composite PK + cascade FKs.

    Both steps are guarded by idempotency probes.
    """
    # ------------------------------------------------------------------
    # Step 1: Rebuild topic table
    # ------------------------------------------------------------------
    topic_cols = _col_names(connection, "topic")
    if "discipline_area_id" not in topic_cols:
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")

        connection.exec_driver_sql(
            """
            CREATE TABLE topic_new (
                id             INTEGER NOT NULL PRIMARY KEY,
                discipline_area_id INTEGER NOT NULL
                    REFERENCES discipline_area(id) ON DELETE RESTRICT,
                name           VARCHAR(120) NOT NULL,
                serial_number  INTEGER NOT NULL,
                UNIQUE (discipline_area_id, serial_number)
            )
            """
        )

        # Live DB has 0 topic rows — no INSERT needed.
        # Defensive copy in case of unexpected rows with non-null main_topic_id
        # would fail the NOT NULL constraint on discipline_area_id; skip it.

        connection.exec_driver_sql("DROP TABLE topic")
        connection.exec_driver_sql("ALTER TABLE topic_new RENAME TO topic")

        connection.exec_driver_sql("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------------
    # Step 2: Create main_topic_syllabus
    # ------------------------------------------------------------------
    if not _table_exists(connection, "main_topic_syllabus"):
        connection.exec_driver_sql(
            """
            CREATE TABLE main_topic_syllabus (
                main_topic_id INTEGER NOT NULL,
                topic_id      INTEGER NOT NULL,
                week_no       INTEGER,
                order_no      INTEGER NOT NULL,
                PRIMARY KEY (main_topic_id, topic_id),
                FOREIGN KEY (main_topic_id)
                    REFERENCES main_topic(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id)
                    REFERENCES topic(id) ON DELETE CASCADE
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_main_topic_syllabus_topic "
            "ON main_topic_syllabus (topic_id)"
        )
