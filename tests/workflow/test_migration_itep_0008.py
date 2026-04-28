"""Tests for the ITEP-0008 schema migration."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from workflow.db.engine import (
    get_global_engine,
    get_global_session,
    init_global_db,
)
from workflow.db.migrations.itep_0008 import (
    BackfillRequest,
    run_migration,
)
from workflow.db.models.academic import MainTopic
from workflow.db.models.project import GeneralProject


@pytest.fixture
def fresh_engine(tmp_path: Path):
    """Engine created via the current ORM metadata (post-ITEP-0008 columns)."""
    engine = get_global_engine(db_path=tmp_path / "fresh.db")
    init_global_db(engine)
    return engine


@pytest.fixture
def legacy_engine(tmp_path: Path):
    """Engine with a pre-ITEP-0008 schema shape (no parent_id, no new gp cols)."""
    engine = get_global_engine(db_path=tmp_path / "legacy.db")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE main_topic (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    code VARCHAR(10) NOT NULL UNIQUE,
                    ddc_mds VARCHAR(20) DEFAULT ''
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE general_project (
                    id INTEGER PRIMARY KEY,
                    main_topic_id INTEGER NOT NULL UNIQUE
                        REFERENCES main_topic(id),
                    abs_parent_dir VARCHAR(500) NOT NULL,
                    abs_src_dir VARCHAR(500) NOT NULL,
                    created_at DATETIME,
                    last_modification DATETIME,
                    version VARCHAR(20) DEFAULT '1.0.0'
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO main_topic (name, code) VALUES "
                "('Nuclear Physics legacy', '0060NP25SF')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO general_project "
                "(main_topic_id, abs_parent_dir, abs_src_dir) "
                "VALUES (1, '/p', '/s')"
            )
        )
    return engine


class TestFreshDatabase:
    def test_run_migration_is_noop_on_fresh_db(self, fresh_engine):
        report = run_migration(fresh_engine)
        # Fresh DBs already include every new column via create_all.
        assert report.columns_added == []
        assert "discipline_area" not in report.tables_created

    def test_discipline_area_exists_after_init(self, fresh_engine):
        run_migration(fresh_engine)
        tables = set(inspect(fresh_engine).get_table_names())
        assert "discipline_area" in tables


class TestLegacyDatabase:
    def test_adds_missing_columns(self, legacy_engine):
        report = run_migration(legacy_engine)
        added = set(report.columns_added)
        assert "main_topic.parent_id" in added
        assert {
            "general_project.year_init",
            "general_project.project_initials",
            "general_project.title",
            "general_project.status",
            "general_project.archived_at",
        }.issubset(added)
        assert "discipline_area" in report.tables_created

    def test_idempotent_on_rerun(self, legacy_engine):
        run_migration(legacy_engine)
        report = run_migration(legacy_engine)
        assert report.columns_added == []
        assert report.tables_created == []

    def test_backfill_creates_area_and_reassigns_child(self, legacy_engine):
        request = BackfillRequest(
            area_code="0060NP",
            area_name="Nuclear Physics",
            children=(("0060NP25SF", 25, "SF", "ScintillatingFibers"),),
        )
        report = run_migration(legacy_engine, backfill=request)
        assert "0060NP" in report.areas_created
        assert "0060NP25SF" in report.children_reassigned
        assert "0060NP25SF" in report.projects_backfilled

        session = get_global_session(legacy_engine)
        try:
            area = session.query(MainTopic).filter_by(code="0060NP").one()
            child = session.query(MainTopic).filter_by(code="0060NP25SF").one()
            assert child.parent_id == area.id
            assert area.parent_id is None
            gp = session.query(GeneralProject).one()
            assert gp.year_init == 25
            assert gp.project_initials == "SF"
            assert gp.title == "ScintillatingFibers"
            assert gp.status == "active"
            assert gp.root_dir == "0060NP-25SF-ScintillatingFibers"
        finally:
            session.close()

    def test_double_backfill_is_idempotent(self, legacy_engine):
        request = BackfillRequest(
            area_code="0060NP",
            area_name="Nuclear Physics",
            children=(("0060NP25SF", 25, "SF", "ScintillatingFibers"),),
        )
        run_migration(legacy_engine, backfill=request)
        report = run_migration(legacy_engine, backfill=request)
        assert report.areas_created == []
        assert report.children_reassigned == []
        assert report.projects_backfilled == []

    def test_backfill_self_reassignment_short_circuits(self, legacy_engine):
        # child.code == area_code -> child resolves to area itself, must skip.
        request = BackfillRequest(
            area_code="0060NP25SF",  # the only legacy MainTopic in fixture
            area_name="Self",
            children=(("0060NP25SF", 25, "SF", "ScintillatingFibers"),),
        )
        report = run_migration(legacy_engine, backfill=request)
        assert "0060NP25SF" in report.children_skipped
        assert report.children_reassigned == []

    def test_backfill_child_without_general_project(self, legacy_engine):
        # Drop the gp row so the child has no linked project.
        with legacy_engine.begin() as conn:
            conn.execute(text("DELETE FROM general_project"))
        request = BackfillRequest(
            area_code="0060NP",
            area_name="Nuclear Physics",
            children=(("0060NP25SF", 25, "SF", "ScintillatingFibers"),),
        )
        report = run_migration(legacy_engine, backfill=request)
        assert "0060NP25SF" in report.children_reassigned
        assert report.projects_backfilled == []

    def test_columns_skipped_on_second_run(self, legacy_engine):
        run_migration(legacy_engine)
        report = run_migration(legacy_engine)
        # Five general_project + one main_topic column already present.
        assert len(report.columns_skipped) == 6

    def test_backfill_skips_unknown_child(self, legacy_engine):
        request = BackfillRequest(
            area_code="0060NP",
            area_name="Nuclear Physics",
            children=(("9999XX99XX", 25, "XX", "Unknown"),),
        )
        report = run_migration(legacy_engine, backfill=request)
        assert "9999XX99XX" in report.children_skipped
        assert report.children_reassigned == []
