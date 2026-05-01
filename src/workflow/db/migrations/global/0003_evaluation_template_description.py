"""0003_evaluation_template_description — add EvaluationTemplate.description.

Pre-existing global DBs (created before the model gained
``description: Mapped[str]`` in ``academic.py``) crash with
``no such column: evaluation_template.description`` on
``workflow evaluations list``. This migration ADDs the column with
default empty-string to match the ORM declaration.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0003_evaluation_template_description"
description: str = "Add evaluation_template.description column."
base: str = "global"


def upgrade(connection: Connection) -> None:
    rows = connection.exec_driver_sql(
        "PRAGMA table_info(evaluation_template)"
    ).fetchall()
    cols = {r[1] for r in rows}
    if "description" not in cols:
        connection.exec_driver_sql(
            "ALTER TABLE evaluation_template "
            "ADD COLUMN description VARCHAR(500) NOT NULL DEFAULT ''"
        )
