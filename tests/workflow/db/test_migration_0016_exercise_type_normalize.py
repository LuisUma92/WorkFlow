"""Tests for migration 0016_exercise_type_normalize_legacy_codes."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0016_exercise_type_normalize_legacy_codes"
    )


@pytest.fixture
def legacy_engine():
    """Minimal exercise table pre-migration, seeded with both literal forms."""
    eng = create_engine("sqlite:///:memory:")
    with eng.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE exercise ("
            "  id INTEGER PRIMARY KEY,"
            "  exercise_id VARCHAR(100),"
            "  type VARCHAR(20)"
            ")"
        )
        conn.exec_driver_sql(
            "INSERT INTO exercise (exercise_id, type) VALUES "
            "('e-code-tsu', 'TSU'), "
            "('e-code-trc', 'TRC'), "
            "('e-code-tde', 'TDE'), "
            "('e-code-tnu', 'TNU'), "
            "('e-code-tvf', 'TVF'), "
            "('e-value-essay', 'essay'), "
            "('e-value-multi', 'multichoice'), "
            "('e-null', NULL)"
        )
        conn.commit()
    return eng


def test_upgrade_normalizes_legacy_codes_to_values(legacy_engine):
    mod = _load()
    with legacy_engine.begin() as conn:
        mod.upgrade(conn)

    with legacy_engine.connect() as conn:
        rows = dict(
            conn.exec_driver_sql(
                "SELECT exercise_id, type FROM exercise"
            ).fetchall()
        )

    assert rows["e-code-tsu"] == "multichoice"
    assert rows["e-code-trc"] == "shortanswer"
    assert rows["e-code-tde"] == "essay"
    assert rows["e-code-tnu"] == "numerical"
    assert rows["e-code-tvf"] == "truefalse"
    # Already-normalized rows are untouched.
    assert rows["e-value-essay"] == "essay"
    assert rows["e-value-multi"] == "multichoice"
    assert rows["e-null"] is None


def test_upgrade_idempotent(legacy_engine):
    mod = _load()
    with legacy_engine.begin() as conn:
        mod.upgrade(conn)
    with legacy_engine.begin() as conn:
        mod.upgrade(conn)  # second run must be a no-op, not an error

    with legacy_engine.connect() as conn:
        rows = dict(
            conn.exec_driver_sql(
                "SELECT exercise_id, type FROM exercise"
            ).fetchall()
        )
    assert rows["e-code-tde"] == "essay"


def test_upgrade_noop_when_exercise_table_absent():
    eng = create_engine("sqlite:///:memory:")
    mod = _load()
    with eng.begin() as conn:
        mod.upgrade(conn)  # must not raise
