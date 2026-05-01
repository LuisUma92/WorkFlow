"""Tests for migration 0003_evaluation_template_description (ITEP-0010 Phase 1C)."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, inspect, text


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0003_evaluation_template_description"
    )


@pytest.fixture
def pre_desc_engine():
    """Engine with evaluation_template missing the `description` column."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE evaluation_template ("
            " id INTEGER PRIMARY KEY,"
            " institution_id INTEGER,"
            " name VARCHAR(80),"
            " template_file VARCHAR(300) DEFAULT ''"
            ")"
        )
        conn.exec_driver_sql(
            "INSERT INTO evaluation_template (institution_id, name)"
            " VALUES (1, 'Quiz')"
        )
    return eng


def test_metadata():
    mod = _load()
    assert mod.revision == "0003_evaluation_template_description"
    assert mod.base == "global"


def test_upgrade_adds_description_column(pre_desc_engine):
    mod = _load()
    with pre_desc_engine.begin() as conn:
        mod.upgrade(conn)
    cols = {c["name"] for c in inspect(pre_desc_engine).get_columns("evaluation_template")}
    assert "description" in cols


def test_upgrade_existing_rows_get_empty_string(pre_desc_engine):
    mod = _load()
    with pre_desc_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_desc_engine.begin() as conn:
        row = conn.execute(
            text("SELECT description FROM evaluation_template WHERE name='Quiz'")
        ).one()
    assert row.description == ""


def test_upgrade_idempotent(pre_desc_engine):
    mod = _load()
    with pre_desc_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_desc_engine.begin() as conn:
        mod.upgrade(conn)  # must not raise on second run
    cols = {c["name"] for c in inspect(pre_desc_engine).get_columns("evaluation_template")}
    assert "description" in cols
