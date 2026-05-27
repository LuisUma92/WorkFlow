"""0010_course_evaluation_practice_cols — add practice/quiz columns to course_evaluation.

Adds four changes to ``course_evaluation``:
  - ``practice_type`` VARCHAR(20):  'practice' | 'quiz'  (nullable)
  - ``practice_name`` VARCHAR(200): human-readable title (nullable)
  - ``source_file``   VARCHAR(300): optional path to .xml / .tex source (nullable)
  - Makes ``evaluation_id`` effectively optional by allowing NULL via a
    table-rebuild (SQLite does not support DROP NOT NULL directly; we do a
    CREATE + INSERT + DROP + RENAME swap).

Pre-existing rows keep NULL in the three new columns.
All steps are idempotent.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0010_course_evaluation_practice_cols"
description: str = (
    "Add practice_type, practice_name, source_file columns to course_evaluation; "
    "make evaluation_id nullable."
)
base: str = "global"


def upgrade(connection: Connection) -> None:
    rows = connection.exec_driver_sql(
        "PRAGMA table_info(course_evaluation)"
    ).fetchall()
    existing = {r[1] for r in rows}

    if "practice_type" not in existing:
        connection.exec_driver_sql(
            "ALTER TABLE course_evaluation ADD COLUMN practice_type VARCHAR(20)"
        )
    if "practice_name" not in existing:
        connection.exec_driver_sql(
            "ALTER TABLE course_evaluation ADD COLUMN practice_name VARCHAR(200)"
        )
    if "source_file" not in existing:
        connection.exec_driver_sql(
            "ALTER TABLE course_evaluation ADD COLUMN source_file VARCHAR(300)"
        )

    # Make evaluation_id nullable via table rebuild (SQLite limitation).
    # Check if the column is currently NOT NULL by inspecting the 'notnull' flag (index 3).
    col_info = {r[1]: r for r in rows}
    eval_col = col_info.get("evaluation_id")
    if eval_col is not None and eval_col[3] == 1:  # notnull == 1 means NOT NULL
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
            """
            CREATE TABLE course_evaluation_new (
                id INTEGER NOT NULL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES course(id),
                evaluation_id INTEGER REFERENCES evaluation_template(id),
                serial_number INTEGER NOT NULL DEFAULT 1,
                percentage REAL NOT NULL DEFAULT 0.0,
                evaluation_week INTEGER NOT NULL DEFAULT 1,
                practice_type VARCHAR(20),
                practice_name VARCHAR(200),
                source_file VARCHAR(300),
                CONSTRAINT ck_pct_range CHECK (percentage >= 0 AND percentage <= 1)
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO course_evaluation_new
                (id, course_id, evaluation_id, serial_number, percentage,
                 evaluation_week, practice_type, practice_name, source_file)
            SELECT id, course_id, evaluation_id, serial_number, percentage,
                   evaluation_week, practice_type, practice_name, source_file
            FROM course_evaluation
            """
        )
        connection.exec_driver_sql("DROP TABLE course_evaluation")
        connection.exec_driver_sql(
            "ALTER TABLE course_evaluation_new RENAME TO course_evaluation"
        )
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
