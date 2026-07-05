"""0016_exercise_type_normalize_legacy_codes — normalize exercise.type.

Bug: ``workflow graph stats`` (and any read of ``Exercise.type``) crashed
with ``LookupError: 'essay' is not among the defined enum values`` because
the live global DB mixes two literal forms in ``exercise.type``:

  - human-readable values (``essay``, ``multichoice``, ...) — the dominant
    form (2986/3391 rows on the live vault DB as of 2026-07-05), matching
    ``ExerciseType.value`` and what CLI choices are built from.
  - short codes (``TDE``, ``TRC``, ``TSU``) — a minority (405/3391 rows),
    matching ``ExerciseType.name``, from an older write path.

``ExerciseType`` (``workflow.exercise.domain``) is the single source of
truth for exercise-type vocabulary. This migration normalizes the minority
code-form rows to their value-form equivalent so the whole column is one
consistent literal family. Paired with reconfiguring the ORM ``Enum`` column
(``values_callable``) to read/write by ``.value``, this makes every row
resolvable. Idempotent: an UPDATE ... WHERE type=<code> is a no-op once no
rows carry the legacy code.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0016_exercise_type_normalize_legacy_codes"
description: str = (
    "Normalize legacy exercise.type code values (TDE/TRC/TSU/TNU/TVF) to "
    "their ExerciseType.value form (essay/shortanswer/multichoice/"
    "numerical/truefalse) — single literal vocabulary."
)
base: str = "global"

# name -> value, mirrors workflow.exercise.domain.ExerciseType 1:1.
# Kept as a plain literal map here (migrations must not import
# application/domain modules — ADR-0010, ITEP-0010 forward-only convention)
# so this migration keeps working even if the enum's Python definition
# changes later.
_LEGACY_CODE_TO_VALUE = {
    "TSU": "multichoice",
    "TRC": "shortanswer",
    "TDE": "essay",
    "TNU": "numerical",
    "TVF": "truefalse",
}


def _table_exists(connection: Connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def upgrade(connection: Connection) -> None:
    if not _table_exists(connection, "exercise"):
        return  # no exercise table yet — nothing to normalize

    for code, value in _LEGACY_CODE_TO_VALUE.items():
        connection.exec_driver_sql(
            "UPDATE exercise SET type = ? WHERE type = ?", (value, code)
        )
