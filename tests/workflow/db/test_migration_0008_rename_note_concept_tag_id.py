"""Tests for migration 0008_rename_note_concept_tag_id."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, inspect, text


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0008_rename_note_concept_tag_id"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_names(engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _fk_targets(engine, table: str) -> set[str]:
    """Return set of 'referred_table.referred_columns[0]' strings."""
    return {
        f"{fk['referred_table']}.{fk['referred_columns'][0]}"
        for fk in inspect(engine).get_foreign_keys(table)
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def legacy_engine():
    """DB with old note_concept(note_id, tag_id) schema."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE note (id INTEGER PRIMARY KEY, title VARCHAR(200))"
        )
        conn.exec_driver_sql(
            "CREATE TABLE concept (id INTEGER PRIMARY KEY, code VARCHAR(60))"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE note_concept (
                note_id    INTEGER NOT NULL REFERENCES note(id)    ON DELETE CASCADE,
                tag_id     INTEGER NOT NULL REFERENCES concept(id) ON DELETE CASCADE,
                PRIMARY KEY (note_id, tag_id)
            )
            """
        )
        conn.exec_driver_sql("INSERT INTO note (id, title) VALUES (1, 'N1')")
        conn.exec_driver_sql("INSERT INTO concept (id, code) VALUES (10, 'algebra')")
        conn.exec_driver_sql(
            "INSERT INTO note_concept (note_id, tag_id) VALUES (1, 10)"
        )
    return eng


@pytest.fixture
def fresh_engine():
    """DB already using the new note_concept(note_id, concept_id) schema."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE note (id INTEGER PRIMARY KEY, title VARCHAR(200))"
        )
        conn.exec_driver_sql(
            "CREATE TABLE concept (id INTEGER PRIMARY KEY, code VARCHAR(60))"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE note_concept (
                note_id    INTEGER NOT NULL REFERENCES note(id)    ON DELETE CASCADE,
                concept_id INTEGER NOT NULL REFERENCES concept(id) ON DELETE CASCADE,
                PRIMARY KEY (note_id, concept_id)
            )
            """
        )
    return eng


@pytest.fixture
def empty_engine():
    """DB with no note_concept table at all."""
    return create_engine("sqlite:///:memory:")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_metadata():
    mod = _load()
    assert mod.revision == "0008_rename_note_concept_tag_id"
    assert mod.base == "global"


# ---------------------------------------------------------------------------
# Legacy path
# ---------------------------------------------------------------------------

def test_legacy_column_renamed(legacy_engine):
    with legacy_engine.begin() as conn:
        _load().upgrade(conn)
    cols = _col_names(legacy_engine, "note_concept")
    assert "concept_id" in cols
    assert "tag_id" not in cols


def test_legacy_row_preserved(legacy_engine):
    with legacy_engine.begin() as conn:
        _load().upgrade(conn)
    with legacy_engine.begin() as conn:
        row = conn.execute(
            text("SELECT note_id, concept_id FROM note_concept")
        ).one()
    assert row.note_id == 1
    assert row.concept_id == 10


def test_legacy_fk_to_concept(legacy_engine):
    with legacy_engine.begin() as conn:
        _load().upgrade(conn)
    fk_targets = _fk_targets(legacy_engine, "note_concept")
    assert "concept.id" in fk_targets


def test_legacy_idempotent(legacy_engine):
    mod = _load()
    with legacy_engine.begin() as conn:
        mod.upgrade(conn)
    with legacy_engine.begin() as conn:
        mod.upgrade(conn)
    cols = _col_names(legacy_engine, "note_concept")
    assert "concept_id" in cols
    assert "tag_id" not in cols


# ---------------------------------------------------------------------------
# Fresh path (no-op)
# ---------------------------------------------------------------------------

def test_fresh_noop(fresh_engine):
    """upgrade() is a no-op when concept_id already exists."""
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)
    cols = _col_names(fresh_engine, "note_concept")
    assert "concept_id" in cols
    assert "tag_id" not in cols


# ---------------------------------------------------------------------------
# No-table path (no-op)
# ---------------------------------------------------------------------------

def test_no_table_noop(empty_engine):
    """upgrade() raises no error when note_concept table is absent."""
    mod = _load()
    with empty_engine.begin() as conn:
        mod.upgrade(conn)
    tables = inspect(empty_engine).get_table_names()
    assert "note_concept" not in tables
