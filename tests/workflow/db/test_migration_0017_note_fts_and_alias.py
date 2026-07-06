"""Tests for migration 0017_note_fts_and_alias (ADR-0021 + ITEP-0015 SS F)."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, inspect


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0017_note_fts_and_alias"
    )


@pytest.fixture
def fresh_engine():
    """A DB with the note table already present (fresh-schema path)."""
    eng = create_engine("sqlite:///:memory:")
    with eng.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE note ("
            "  id INTEGER PRIMARY KEY,"
            "  filename VARCHAR,"
            "  title VARCHAR"
            ")"
        )
        conn.commit()
    return eng


def test_upgrade_creates_note_fts_table(fresh_engine):
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)

    insp = inspect(fresh_engine)
    assert "note_fts" in insp.get_table_names()


def test_upgrade_creates_note_alias_table(fresh_engine):
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)

    insp = inspect(fresh_engine)
    assert "note_alias" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("note_alias")}
    assert {"id", "note_id", "alias"} <= cols


def test_note_fts_supports_insert_and_match_query(fresh_engine):
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)

    with fresh_engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO note_fts(rowid, title, aliases, body) VALUES (?, ?, ?, ?)",
            (1, "Gauss's Law", "", "Gauss law states that flux equals..."),
        )

    with fresh_engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT rowid FROM note_fts WHERE note_fts MATCH 'gauss'"
        ).fetchall()
    assert rows and rows[0][0] == 1


def test_note_fts_remove_diacritics_matches_accented_query(fresh_engine):
    """Spanish accents/ñ must be query-insensitive (remove_diacritics=2)."""
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)

    with fresh_engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO note_fts(rowid, title, aliases, body) VALUES (?, ?, ?, ?)",
            (1, "Teoria de Campos", "", "cuerpo de la nota sobre campos"),
        )

    with fresh_engine.connect() as conn:
        # Query with accent must find the unaccented indexed title.
        rows = conn.exec_driver_sql(
            "SELECT rowid FROM note_fts WHERE note_fts MATCH 'teoría'"
        ).fetchall()
    assert rows and rows[0][0] == 1


def test_note_alias_unique_constraint_enforced(fresh_engine):
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)
        conn.exec_driver_sql(
            "INSERT INTO note (id, filename, title) VALUES (1, 'a.md', 'A')"
        )
        conn.exec_driver_sql(
            "INSERT INTO note_alias (note_id, alias) VALUES (1, 'alias-a')"
        )

    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with fresh_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO note_alias (note_id, alias) VALUES (1, 'alias-a')"
            )


def test_upgrade_idempotent(fresh_engine):
    mod = _load()
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)
    with fresh_engine.begin() as conn:
        mod.upgrade(conn)  # second run must be a no-op, not an error

    insp = inspect(fresh_engine)
    assert "note_fts" in insp.get_table_names()
    assert "note_alias" in insp.get_table_names()


def test_upgrade_on_schema_with_no_note_table_yet():
    """A legacy-migrated DB may run this before 'note' physically exists in
    the connection's visible schema (e.g. a bare in-memory engine in a
    unit test) — note_alias's FK reference does not require note to
    pre-exist for CREATE TABLE itself (SQLite does not validate FK targets
    at DDL time); this must not raise.
    """
    eng = create_engine("sqlite:///:memory:")
    mod = _load()
    with eng.begin() as conn:
        mod.upgrade(conn)  # must not raise
    insp = inspect(eng)
    assert "note_fts" in insp.get_table_names()
    assert "note_alias" in insp.get_table_names()
