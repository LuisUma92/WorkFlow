"""Tests for migration 0002_main_topic_discipline_area_fk (ITEP-0010 / ITEP-0008)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def pre_fk_engine():
    """Engine with main_topic + discipline_area shaped as ITEP-0008-clean (no FK)."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE discipline_area ("
            " id INTEGER PRIMARY KEY,"
            " code VARCHAR(6) UNIQUE,"
            " name VARCHAR(120),"
            " dewey VARCHAR(20) DEFAULT '',"
            " discipline_num INTEGER,"
            " topic_num INTEGER,"
            " area_initials VARCHAR(2)"
            ")"
        )
        conn.exec_driver_sql(
            "CREATE TABLE main_topic ("
            " id INTEGER PRIMARY KEY,"
            " name VARCHAR(120),"
            " code VARCHAR(10) UNIQUE,"
            " ddc_mds VARCHAR(20) DEFAULT '',"
            " parent_id INTEGER REFERENCES main_topic(id)"
            ")"
        )
    return eng


def _load_migration():
    import importlib

    return importlib.import_module(
        "workflow.db.migrations.global.0002_main_topic_discipline_area_fk"
    )


def test_revision_metadata():
    mod = _load_migration()
    assert mod.revision == "0002_main_topic_discipline_area_fk"
    assert mod.base == "global"
    assert "discipline_area" in mod.description.lower()


def test_upgrade_adds_column(pre_fk_engine):
    mod = _load_migration()
    with pre_fk_engine.begin() as conn:
        mod.upgrade(conn)
    cols = {c["name"] for c in inspect(pre_fk_engine).get_columns("main_topic")}
    assert "discipline_area_id" in cols


def test_upgrade_backfills_from_code_prefix(pre_fk_engine):
    with pre_fk_engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO discipline_area"
            " (code, name, discipline_num, topic_num, area_initials)"
            " VALUES ('0010MC', 'Mecánica', 0, 10, 'MC')"
        )
        conn.exec_driver_sql(
            "INSERT INTO main_topic (name, code) VALUES ('Mecánica', '0010MC')"
        )
        conn.exec_driver_sql(
            "INSERT INTO main_topic (name, code, parent_id)"
            " VALUES ('Project', '0010MC26AB', 1)"
        )

    mod = _load_migration()
    with pre_fk_engine.begin() as conn:
        mod.upgrade(conn)

    with pre_fk_engine.begin() as conn:
        rows = conn.execute(
            text("SELECT code, discipline_area_id FROM main_topic ORDER BY id")
        ).all()
    assert rows[0].discipline_area_id == 1
    assert rows[1].discipline_area_id == 1  # inherited via prefix match


def test_upgrade_idempotent(pre_fk_engine):
    mod = _load_migration()
    with pre_fk_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_fk_engine.begin() as conn:
        mod.upgrade(conn)  # second call must not raise
    cols = {c["name"] for c in inspect(pre_fk_engine).get_columns("main_topic")}
    assert "discipline_area_id" in cols


def test_upgrade_no_orphan_backfill_when_catalog_missing(pre_fk_engine):
    """Rows whose code prefix has no DisciplineArea stay NULL (data fix-up out of scope)."""
    with pre_fk_engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO main_topic (name, code) VALUES ('Orphan', 'XXXXXX')"
        )
    mod = _load_migration()
    with pre_fk_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_fk_engine.begin() as conn:
        row = conn.execute(
            text("SELECT discipline_area_id FROM main_topic WHERE code='XXXXXX'")
        ).one()
    assert row.discipline_area_id is None
