"""Tests for migration 0011_topic_root_discipline_area.

Validates:
- topic table is rebuilt: main_topic_id dropped, discipline_area_id added
- Unique constraint (discipline_area_id, serial_number) enforced after migration
- main_topic_syllabus table created with composite PK + two CASCADE FKs
- Idempotency (apply twice, no error, no drift)
- Zero topic rows preserved (structural-only migration)
- Migration appears in discovery
"""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, inspect, text


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0011_topic_root_discipline_area"
    )


# ---------------------------------------------------------------------------
# Helpers (mirror 0009 pattern)
# ---------------------------------------------------------------------------


def _col_names(engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _fk_targets(engine, table: str) -> list[dict]:
    return inspect(engine).get_foreign_keys(table)


def _table_exists(connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _index_names(engine, table: str) -> set[str]:
    return {idx["name"] for idx in inspect(engine).get_indexes(table)}


# ---------------------------------------------------------------------------
# Pre-0011 schema seed  (topic still has main_topic_id)
# ---------------------------------------------------------------------------


def _seed_pre_0011_schema(conn):
    """Create the schema as it existed just before migration 0011.

    Key characteristics:
      - discipline_area table exists
      - main_topic table exists
      - topic has main_topic_id FK → main_topic.id  (NOT discipline_area_id)
      - main_topic_syllabus table does NOT exist
    """
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS discipline_area ("
        "  id INTEGER PRIMARY KEY, code VARCHAR(6), name VARCHAR(120),"
        "  dewey VARCHAR(20), discipline_num INTEGER, topic_num INTEGER,"
        "  area_initials VARCHAR(2)"
        ")"
    )
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS main_topic ("
        "  id INTEGER PRIMARY KEY, name VARCHAR(120), code VARCHAR(10),"
        "  ddc_mds VARCHAR(20), parent_id INTEGER, discipline_area_id INTEGER"
        "  REFERENCES discipline_area(id)"
        ")"
    )
    # OLD topic — rooted at main_topic, no discipline_area_id
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS topic ("
        "  id INTEGER PRIMARY KEY,"
        "  main_topic_id INTEGER REFERENCES main_topic(id),"
        "  name VARCHAR(120),"
        "  serial_number INTEGER"
        ")"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pre_engine():
    """In-memory DB seeded with the pre-0011 schema."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        _seed_pre_0011_schema(conn)
    return eng


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestMigration0011TopicRootDisciplineArea:

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------

    def test_metadata(self):
        mod = _load()
        assert mod.revision == "0011_topic_root_discipline_area"
        assert mod.base == "global"

    # ------------------------------------------------------------------
    # 2. topic table rebuilt: main_topic_id gone, discipline_area_id added
    # ------------------------------------------------------------------

    def test_migration_drops_topic_main_topic_id_adds_discipline_area_id(
        self, pre_engine
    ):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        cols = _col_names(pre_engine, "topic")
        assert "discipline_area_id" in cols, (
            "topic must gain discipline_area_id after migration"
        )
        assert "main_topic_id" not in cols, (
            "topic must NOT have main_topic_id after migration"
        )
        # Verify FK to discipline_area
        fks = _fk_targets(pre_engine, "topic")
        da_fk = [fk for fk in fks if fk["referred_table"] == "discipline_area"]
        assert da_fk, "topic must have FK → discipline_area after migration"

    # ------------------------------------------------------------------
    # 3. Unique constraint (discipline_area_id, serial_number)
    # ------------------------------------------------------------------

    def test_migration_unique_constraint_discipline_area_serial(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO discipline_area (id, code, name, dewey, "
                "discipline_num, topic_num, area_initials) "
                "VALUES (1, 'FI0101', 'Physics', '530', 1, 1, 'FI')"
            )
            conn.exec_driver_sql(
                "INSERT INTO topic (id, discipline_area_id, name, serial_number) "
                "VALUES (1, 1, 'Kinematics', 1)"
            )

        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            with pre_engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT INTO topic (id, discipline_area_id, name, serial_number) "
                    "VALUES (2, 1, 'Dynamics', 1)"
                )

    # ------------------------------------------------------------------
    # 4. main_topic_syllabus table created with composite PK + 2 cascade FKs
    # ------------------------------------------------------------------

    def test_migration_creates_main_topic_syllabus_table(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        with pre_engine.connect() as conn:
            assert _table_exists(conn, "main_topic_syllabus"), (
                "main_topic_syllabus must exist after migration"
            )

        cols = _col_names(pre_engine, "main_topic_syllabus")
        assert {"main_topic_id", "topic_id", "week_no", "order_no"}.issubset(cols), (
            f"main_topic_syllabus columns incomplete: {cols}"
        )

        fks = _fk_targets(pre_engine, "main_topic_syllabus")
        mt_fk = [fk for fk in fks if fk["referred_table"] == "main_topic"]
        topic_fk = [fk for fk in fks if fk["referred_table"] == "topic"]
        assert mt_fk, "main_topic_syllabus must have FK → main_topic"
        assert topic_fk, "main_topic_syllabus must have FK → topic"

        # Index on topic_id exists
        idx_names = _index_names(pre_engine, "main_topic_syllabus")
        assert "ix_main_topic_syllabus_topic" in idx_names, (
            f"Index ix_main_topic_syllabus_topic missing; found: {idx_names}"
        )

    # ------------------------------------------------------------------
    # 5. Cascade: deleting main_topic removes syllabus row
    # ------------------------------------------------------------------

    def test_migration_cascade_delete_main_topic(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO discipline_area (id, code, name, dewey, "
                "discipline_num, topic_num, area_initials) "
                "VALUES (1, 'FI0101', 'Physics', '530', 1, 1, 'FI')"
            )
            conn.exec_driver_sql(
                "INSERT INTO main_topic (id, name, code, ddc_mds, discipline_area_id) "
                "VALUES (1, 'Mechanics', 'FI01', '', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO topic (id, discipline_area_id, name, serial_number) "
                "VALUES (1, 1, 'Kinematics', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO main_topic_syllabus "
                "(main_topic_id, topic_id, week_no, order_no) VALUES (1, 1, 1, 1)"
            )

        with pre_engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM main_topic WHERE id = 1")

        with pre_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM main_topic_syllabus")
            ).scalar()
        assert count == 0, "Syllabus rows must be deleted when MainTopic is deleted"

    # ------------------------------------------------------------------
    # 6. Cascade: deleting topic removes syllabus row
    # ------------------------------------------------------------------

    def test_migration_cascade_delete_topic(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO discipline_area (id, code, name, dewey, "
                "discipline_num, topic_num, area_initials) "
                "VALUES (1, 'FI0101', 'Physics', '530', 1, 1, 'FI')"
            )
            conn.exec_driver_sql(
                "INSERT INTO main_topic (id, name, code, ddc_mds, discipline_area_id) "
                "VALUES (1, 'Mechanics', 'FI01', '', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO topic (id, discipline_area_id, name, serial_number) "
                "VALUES (1, 1, 'Kinematics', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO main_topic_syllabus "
                "(main_topic_id, topic_id, week_no, order_no) VALUES (1, 1, 1, 1)"
            )

        with pre_engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM topic WHERE id = 1")

        with pre_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM main_topic_syllabus")
            ).scalar()
        assert count == 0, "Syllabus rows must be deleted when Topic is deleted"

    # ------------------------------------------------------------------
    # 7. Idempotency
    # ------------------------------------------------------------------

    def test_migration_idempotent(self, pre_engine):
        mod = _load()
        with pre_engine.begin() as conn:
            mod.upgrade(conn)
        # Second run must not raise and schema must remain consistent
        with pre_engine.begin() as conn:
            mod.upgrade(conn)

        cols = _col_names(pre_engine, "topic")
        assert "discipline_area_id" in cols
        assert "main_topic_id" not in cols

        with pre_engine.connect() as conn:
            assert _table_exists(conn, "main_topic_syllabus")

    # ------------------------------------------------------------------
    # 8. Zero topic rows preserved
    # ------------------------------------------------------------------

    def test_migration_preserves_zero_topic_rows(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        with pre_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM topic")).scalar()
        assert count == 0, "topic must still have 0 rows after structural migration"

    # ------------------------------------------------------------------
    # 9. Migration appears in discovery
    # ------------------------------------------------------------------

    def test_migration_in_discovery(self):
        from workflow.db.migrations import discover

        steps = discover("global")
        revisions = [s.revision for s in steps]
        assert "0011_topic_root_discipline_area" in revisions
