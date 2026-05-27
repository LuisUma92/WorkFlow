"""Tests for migration 0009_normalize_models."""

from __future__ import annotations

import importlib
import json

import pytest
from sqlalchemy import create_engine, inspect, text


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0009_normalize_models"
    )


# ---------------------------------------------------------------------------
# Helpers
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
# Pre-migration schema seed
# ---------------------------------------------------------------------------


def _seed_pre_0009_schema(conn):
    """Create the schema as it existed before this migration.

    Based on commit 8591429~1 (the live DB shape):
      - concept(id, main_topic_id, code, label, description, parent_id, created_at)
      - content(id, topic_id, chapter_number, section_number, name,
                first_page, last_page, first_exercise, last_exercise)
      - bib_content(bib_entry_id, content_id)  — link only, no locus columns
      - exercise(..., content_id, concepts, ...)
      - NO exercise_concept table
    """
    # Reference / dependency tables (minimal stubs)
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS discipline_area ("
        "  id INTEGER PRIMARY KEY, code VARCHAR(6), name VARCHAR(120)"
        ")"
    )
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS main_topic ("
        "  id INTEGER PRIMARY KEY, name VARCHAR(120), code VARCHAR(10),"
        "  ddc_mds VARCHAR(20), parent_id INTEGER, discipline_area_id INTEGER"
        ")"
    )
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS topic ("
        "  id INTEGER PRIMARY KEY, main_topic_id INTEGER, name VARCHAR(120),"
        "  serial_number INTEGER"
        ")"
    )
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS bib_entry ("
        "  id INTEGER PRIMARY KEY, title VARCHAR(500)"
        ")"
    )
    # Old content — carries locus columns
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS content ("
        "  id INTEGER PRIMARY KEY,"
        "  topic_id INTEGER,"
        "  chapter_number INTEGER,"
        "  section_number INTEGER,"
        "  name VARCHAR(200),"
        "  first_page INTEGER,"
        "  last_page INTEGER,"
        "  first_exercise INTEGER,"
        "  last_exercise INTEGER"
        ")"
    )
    # Old bib_content — no locus columns
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS bib_content ("
        "  bib_entry_id INTEGER NOT NULL REFERENCES bib_entry(id),"
        "  content_id   INTEGER NOT NULL REFERENCES content(id),"
        "  PRIMARY KEY (bib_entry_id, content_id)"
        ")"
    )
    # Old concept — rooted at main_topic
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS concept ("
        "  id INTEGER PRIMARY KEY,"
        "  main_topic_id INTEGER REFERENCES main_topic(id),"
        "  code VARCHAR(32) UNIQUE,"
        "  label VARCHAR(255),"
        "  description TEXT,"
        "  parent_id INTEGER REFERENCES concept(id),"
        "  created_at DATETIME"
        ")"
    )
    # Old exercise — has concepts JSON and content_id FK
    conn.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS exercise ("
        "  id INTEGER PRIMARY KEY,"
        "  exercise_id VARCHAR(100) UNIQUE,"
        "  source_path TEXT,"
        "  file_hash VARCHAR(64),"
        "  status VARCHAR(20),"
        "  type VARCHAR(20),"
        "  difficulty VARCHAR(10),"
        "  taxonomy_level VARCHAR(30),"
        "  taxonomy_domain VARCHAR(30),"
        "  tags TEXT,"
        "  book_id INTEGER REFERENCES bib_entry(id),"
        "  content_id INTEGER REFERENCES content(id),"
        "  concepts TEXT,"
        "  default_grade REAL,"
        "  penalty REAL,"
        "  has_images INTEGER,"
        "  image_refs TEXT,"
        "  diagram_id VARCHAR(100),"
        "  option_count INTEGER,"
        "  created_at DATETIME,"
        "  updated_at DATETIME"
        ")"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pre_engine():
    """In-memory DB seeded with the pre-0009 schema."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        _seed_pre_0009_schema(conn)
    return eng


# ---------------------------------------------------------------------------
# Class grouping all test cases
# ---------------------------------------------------------------------------


class TestMigration0009NormalizeModels:

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------

    def test_metadata(self):
        mod = _load()
        assert mod.revision == "0009_normalize_models"
        assert mod.base == "global"

    # ------------------------------------------------------------------
    # 2. Concept shape after upgrade
    # ------------------------------------------------------------------

    def test_migration_creates_new_concept_shape(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        cols = _col_names(pre_engine, "concept")
        expected = {"id", "content_id", "domain", "code", "label", "description",
                    "parent_id", "created_at"}
        assert expected == cols
        assert "main_topic_id" not in cols

        # FK from concept.content_id → content.id must exist
        fks = _fk_targets(pre_engine, "concept")
        content_fk = [fk for fk in fks if fk["referred_table"] == "content"]
        assert content_fk, "concept must have a FK to content"
        assert content_fk[0]["referred_columns"] == ["id"]

    # ------------------------------------------------------------------
    # 3. concept CHECK constraint on domain
    # ------------------------------------------------------------------

    def test_migration_concept_has_check_constraint_on_domain(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        # Insert a topic and content row so the FK is satisfiable
        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO topic (id, main_topic_id, name, serial_number) "
                "VALUES (1, NULL, 'T', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content (id, topic_id, name) VALUES (1, 1, 'C')"
            )

        # Bad domain must fail
        from sqlalchemy.exc import IntegrityError
        with pytest.raises((IntegrityError, Exception)):
            with pre_engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT INTO concept (id, content_id, domain, code, label) "
                    "VALUES (1, 1, 'bogus', 'slug-a', 'Label A')"
                )

        # Valid domain must succeed
        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO concept (id, content_id, domain, code, label) "
                "VALUES (2, 1, 'Información', 'slug-b', 'Label B')"
            )
        with pre_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM concept WHERE domain = 'Información'")
            ).scalar()
        assert count == 1

    # ------------------------------------------------------------------
    # 4. Content loses locus columns; rows preserved
    # ------------------------------------------------------------------

    def test_migration_content_drops_locus_columns(self, pre_engine):
        # Seed 2 content rows
        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO topic (id, main_topic_id, name, serial_number) "
                "VALUES (1, NULL, 'Physics', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content (id, topic_id, chapter_number, section_number, "
                "name, first_page, last_page, first_exercise, last_exercise) "
                "VALUES (1, 1, 3, 2, 'Kinematics', 100, 150, 1, 30)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content (id, topic_id, chapter_number, section_number, "
                "name, first_page, last_page, first_exercise, last_exercise) "
                "VALUES (2, 1, 4, 1, 'Dynamics', 151, 200, 31, 60)"
            )

        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        cols = _col_names(pre_engine, "content")
        assert cols == {"id", "topic_id", "name"}
        dropped = {"chapter_number", "section_number", "first_page",
                   "last_page", "first_exercise", "last_exercise"}
        assert not (dropped & cols), f"Dropped columns still present: {dropped & cols}"

        # Both rows preserved
        with pre_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, topic_id, name FROM content ORDER BY id")
            ).fetchall()
        assert len(rows) == 2
        assert rows[0] == (1, 1, "Kinematics")
        assert rows[1] == (2, 1, "Dynamics")

    # ------------------------------------------------------------------
    # 5. BibContent gains locus columns
    # ------------------------------------------------------------------

    def test_migration_bib_content_gains_locus_columns(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        cols = _col_names(pre_engine, "bib_content")
        expected_locus = {"chapter_number", "section_number", "first_page",
                          "last_page", "first_exercise", "last_exercise"}
        assert expected_locus.issubset(cols), (
            f"Missing locus columns: {expected_locus - cols}"
        )
        assert "bib_entry_id" in cols
        assert "content_id" in cols

        # Insert should work
        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO topic (id, main_topic_id, name, serial_number) "
                "VALUES (1, NULL, 'T', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content (id, topic_id, name) VALUES (1, 1, 'C')"
            )
            conn.exec_driver_sql(
                "INSERT INTO bib_entry (id, title) VALUES (1, 'Book A')"
            )
            conn.exec_driver_sql(
                "INSERT INTO bib_content (bib_entry_id, content_id, chapter_number, "
                "section_number, first_page, last_page, first_exercise, last_exercise) "
                "VALUES (1, 1, 2, 3, 10, 50, 1, 20)"
            )
        with pre_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM bib_content")).scalar()
        assert count == 1

    # ------------------------------------------------------------------
    # 6. Exercise drops concepts and content_id; rows preserved
    # ------------------------------------------------------------------

    def test_migration_exercise_drops_concepts_and_content_id(self, pre_engine):
        # Seed 5 exercise rows with mixed data
        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO topic (id, main_topic_id, name, serial_number) "
                "VALUES (1, NULL, 'T', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO content (id, topic_id, chapter_number, section_number, "
                "name, first_page, last_page) VALUES (1, 1, 1, 1, 'C', 1, 10)"
            )
            rows = [
                (1, "ex-001", "/a/001.tex", "abc", "complete", None, None, None, None,
                 None, None, None, '["foo"]', 1.0, 0.0, 0, None, None, 0, None, None),
                (2, "ex-002", "/a/002.tex", "def", "complete", None, None, None, None,
                 None, None, 1, '["bar","baz"]', 2.0, 0.0, 0, None, None, 0, None, None),
                (3, "ex-003", "/a/003.tex", "ghi", "placeholder", None, None, None, None,
                 None, None, None, None, None, 0.0, 0, None, None, 0, None, None),
                (4, "ex-004", "/a/004.tex", "jkl", "complete", None, None, None, None,
                 None, None, None, "[]", 3.0, 0.0, 0, None, None, 0, None, None),
                (5, "ex-005", "/a/005.tex", "mno", "in_progress", None, None, None, None,
                 None, None, None, None, None, 0.0, 0, None, None, 0, None, None),
            ]
            for r in rows:
                conn.exec_driver_sql(
                    "INSERT INTO exercise (id, exercise_id, source_path, file_hash, "
                    "status, type, difficulty, taxonomy_level, taxonomy_domain, tags, "
                    "book_id, content_id, concepts, default_grade, penalty, has_images, "
                    "image_refs, diagram_id, option_count, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    r,
                )

        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        cols = _col_names(pre_engine, "exercise")
        assert "concepts" not in cols
        assert "content_id" not in cols

        # All 5 rows survive
        with pre_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM exercise")).scalar()
        assert count == 5

        # Spot-check preserved fields
        with pre_engine.connect() as conn:
            row = conn.execute(
                text("SELECT exercise_id, file_hash FROM exercise WHERE id = 2")
            ).one()
        assert row.exercise_id == "ex-002"
        assert row.file_hash == "def"

    # ------------------------------------------------------------------
    # 7. exercise_concept table created with correct shape
    # ------------------------------------------------------------------

    def test_migration_creates_exercise_concept_table(self, pre_engine):
        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        with pre_engine.connect() as conn:
            assert _table_exists(conn, "exercise_concept"), (
                "exercise_concept table must exist after migration"
            )

        cols = _col_names(pre_engine, "exercise_concept")
        assert "exercise_id" in cols
        assert "concept_id" in cols

        # Both FKs with CASCADE
        fks = _fk_targets(pre_engine, "exercise_concept")
        exercise_fk = [fk for fk in fks if fk["referred_table"] == "exercise"]
        concept_fk = [fk for fk in fks if fk["referred_table"] == "concept"]
        assert exercise_fk, "exercise_concept must FK to exercise"
        assert concept_fk, "exercise_concept must FK to concept"

        # ix_exercise_concept_concept index exists
        idx_names = _index_names(pre_engine, "exercise_concept")
        assert "ix_exercise_concept_concept" in idx_names

    # ------------------------------------------------------------------
    # 8. Orphan dump file written when exercises have non-empty concepts
    # ------------------------------------------------------------------

    def test_migration_writes_orphan_dump_file(self, pre_engine, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))

        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO exercise (id, exercise_id, source_path, file_hash, "
                "status, penalty, has_images, option_count, concepts) "
                "VALUES (1, 'ex-A', '/x/A.tex', 'aaa', 'complete', 0.0, 0, 0, '[\"foo\"]')"
            )
            conn.exec_driver_sql(
                "INSERT INTO exercise (id, exercise_id, source_path, file_hash, "
                "status, penalty, has_images, option_count, concepts) "
                "VALUES (2, 'ex-B', '/x/B.tex', 'bbb', 'complete', 0.0, 0, 0, '[\"bar\"]')"
            )

        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        # The dump file should exist under the redirected HOME
        dump_path = (
            tmp_path / "01-U" / "workflow"
            / "migration-0009-orphan-exercise-concepts.txt"
        )
        assert dump_path.exists(), f"Orphan dump file not found at {dump_path}"

        content = dump_path.read_text()
        assert "ex-A" in content
        assert "ex-B" in content

    # ------------------------------------------------------------------
    # 9. No orphan dump when no exercises have concepts
    # ------------------------------------------------------------------

    def test_migration_no_orphan_dump_when_no_rows_have_concepts(
        self, pre_engine, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        with pre_engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO exercise (id, exercise_id, source_path, file_hash, "
                "status, penalty, has_images, option_count, concepts) "
                "VALUES (1, 'ex-C', '/x/C.tex', 'ccc', 'complete', 0.0, 0, 0, NULL)"
            )
            conn.exec_driver_sql(
                "INSERT INTO exercise (id, exercise_id, source_path, file_hash, "
                "status, penalty, has_images, option_count, concepts) "
                "VALUES (2, 'ex-D', '/x/D.tex', 'ddd', 'complete', 0.0, 0, 0, '[]')"
            )

        with pre_engine.begin() as conn:
            _load().upgrade(conn)

        dump_path = (
            tmp_path / "01-U" / "workflow"
            / "migration-0009-orphan-exercise-concepts.txt"
        )
        assert not dump_path.exists(), "Orphan dump file must NOT be created when no concepts"

    # ------------------------------------------------------------------
    # 10. Idempotency
    # ------------------------------------------------------------------

    def test_migration_idempotent(self, pre_engine):
        mod = _load()
        with pre_engine.begin() as conn:
            mod.upgrade(conn)
        # Second run must not raise and schema must remain consistent
        with pre_engine.begin() as conn:
            mod.upgrade(conn)

        # Schema checks
        cols_concept = _col_names(pre_engine, "concept")
        assert "content_id" in cols_concept
        assert "main_topic_id" not in cols_concept

        cols_exercise = _col_names(pre_engine, "exercise")
        assert "concepts" not in cols_exercise
        assert "content_id" not in cols_exercise

        with pre_engine.connect() as conn:
            assert _table_exists(conn, "exercise_concept")

    # ------------------------------------------------------------------
    # 11. Migration appears in discovery
    # ------------------------------------------------------------------

    def test_migration_appears_in_discovery(self):
        from workflow.db.migrations import discover

        steps = discover("global")
        revisions = [s.revision for s in steps]
        assert "0009_normalize_models" in revisions
