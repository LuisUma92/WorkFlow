"""0002_main_topic_discipline_area_fk — ITEP-0008 catalog/state FK.

Adds ``main_topic.discipline_area_id`` (FK -> discipline_area.id) and
backfills it for existing rows by matching the first 6 characters of
``main_topic.code`` against ``discipline_area.code``.

SQLite's ALTER TABLE cannot add a NOT NULL column without a default and
cannot retroactively tighten a column to NOT NULL; the ORM declares
``nullable=False`` so fresh DBs (created via ``create_all`` after the
runner stamps head) carry the constraint. Pre-existing DBs end up with a
nullable column at the SQL level after this migration; the ORM enforces
non-null on every insert/update going forward (ADR ITEP-0010).
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0002_main_topic_discipline_area_fk"
description: str = (
    "Add main_topic.discipline_area_id FK to discipline_area "
    "and backfill from code prefix (ITEP-0008 amendment)."
)
base: str = "global"


def upgrade(connection: Connection) -> None:
    insp_rows = connection.exec_driver_sql(
        "PRAGMA table_info(main_topic)"
    ).fetchall()
    existing_cols = {row[1] for row in insp_rows}
    if "discipline_area_id" not in existing_cols:
        connection.exec_driver_sql(
            "ALTER TABLE main_topic ADD COLUMN discipline_area_id INTEGER "
            "REFERENCES discipline_area(id)"
        )

    connection.exec_driver_sql(
        "UPDATE main_topic SET discipline_area_id = ("
        "  SELECT discipline_area.id FROM discipline_area"
        "  WHERE discipline_area.code = SUBSTR(main_topic.code, 1, 6)"
        ") WHERE discipline_area_id IS NULL"
    )
