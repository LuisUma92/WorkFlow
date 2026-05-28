"""Migration 0006_note_main_topic_id — note.main_topic_id nullable FK column.

The spec referenced this as "0012_note_main_topic_fk" but the column was
shipped in migration 0006 (early Phase B). These tests verify the behaviour
described in the Phase 4D scope:

  - migration applies to a legacy DB that lacks the column
  - migration is idempotent (re-running is a no-op)
  - existing note rows are preserved
  - added column is nullable (FK ON DELETE SET NULL)

ADR refs: ITEP-0010 (forward-only migrations), Phase 4D spec.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, inspect, text
import workflow.db.models.academic  # noqa: F401
import workflow.db.models.bibliography  # noqa: F401
import workflow.db.models.exercises  # noqa: F401
import workflow.db.models.notes  # noqa: F401
import workflow.db.models.project  # noqa: F401
import importlib

from workflow.db.engine import init_global_db
from workflow.db.migrations import upgrade

_mod_0006 = importlib.import_module("workflow.db.migrations.global.0006_note_main_topic_id")
upgrade_0006 = _mod_0006.upgrade


def _enable_fk(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@pytest.fixture()
def global_engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/g.db")
    event.listen(eng, "connect", _enable_fk)
    init_global_db(eng)
    return eng


@pytest.fixture()
def legacy_engine(tmp_path):
    """Engine with note table lacking main_topic_id (pre-0006 schema)."""
    eng = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    event.listen(eng, "connect", _enable_fk)
    with eng.connect() as conn:
        # Create minimal schema without main_topic + note.main_topic_id
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS note (
                id INTEGER NOT NULL PRIMARY KEY,
                filename VARCHAR NOT NULL UNIQUE,
                reference VARCHAR NOT NULL UNIQUE
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS main_topic (
                id INTEGER NOT NULL PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                discipline_area_id INTEGER
            )
        """))
        # Insert a note row to verify row preservation after migration
        conn.execute(text(
            "INSERT INTO note (filename, reference) VALUES ('legacy.md', 'legacy')"
        ))
        conn.commit()
    return eng


# ---------------------------------------------------------------------------
# Tests on fully-migrated DB
# ---------------------------------------------------------------------------


class TestMigrationColumn:
    def test_column_present_after_init(self, global_engine):
        insp = inspect(global_engine)
        cols = {c["name"] for c in insp.get_columns("note")}
        assert "main_topic_id" in cols

    def test_column_is_nullable(self, global_engine):
        insp = inspect(global_engine)
        for col in insp.get_columns("note"):
            if col["name"] == "main_topic_id":
                assert col["nullable"] is True
                break

    def test_index_present(self, global_engine):
        insp = inspect(global_engine)
        idx_names = {ix["name"] for ix in insp.get_indexes("note")}
        assert "ix_note_main_topic_id" in idx_names

    def test_migration_idempotent_via_runner(self, global_engine):
        """Running upgrade again marks 0006 as skipped (already applied)."""
        result = upgrade(global_engine, "global")
        assert "0006_note_main_topic_id" in result.skipped


# ---------------------------------------------------------------------------
# Tests on legacy fixture (manual upgrade)
# ---------------------------------------------------------------------------


class TestMigrationOnLegacySchema:
    def test_applies_on_legacy_no_column(self, legacy_engine):
        insp = inspect(legacy_engine)
        pre_cols = {c["name"] for c in insp.get_columns("note")}
        assert "main_topic_id" not in pre_cols

        with legacy_engine.connect() as conn:
            upgrade_0006(conn)
            conn.commit()

        insp2 = inspect(legacy_engine)
        post_cols = {c["name"] for c in insp2.get_columns("note")}
        assert "main_topic_id" in post_cols

    def test_preserves_note_rows(self, legacy_engine):
        with legacy_engine.connect() as conn:
            upgrade_0006(conn)
            conn.commit()
            rows = conn.execute(text("SELECT filename FROM note")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "legacy.md"

    def test_idempotent_on_legacy(self, legacy_engine):
        with legacy_engine.connect() as conn:
            upgrade_0006(conn)
            conn.commit()
        # Second application should not raise
        with legacy_engine.connect() as conn:
            upgrade_0006(conn)
            conn.commit()
        insp = inspect(legacy_engine)
        cols = {c["name"] for c in insp.get_columns("note")}
        assert "main_topic_id" in cols

    def test_column_nullable_after_manual_apply(self, legacy_engine):
        with legacy_engine.connect() as conn:
            upgrade_0006(conn)
            conn.commit()
        insp = inspect(legacy_engine)
        for col in insp.get_columns("note"):
            if col["name"] == "main_topic_id":
                assert col["nullable"] is True
                return
        pytest.fail("main_topic_id column not found after upgrade")
