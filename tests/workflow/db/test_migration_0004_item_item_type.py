"""Tests for migration 0004_item_item_type (ITEP-0010)."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, inspect, text


def _load():
    return importlib.import_module(
        "workflow.db.migrations.global.0004_item_item_type"
    )


@pytest.fixture
def pre_engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE item ("
            " id INTEGER PRIMARY KEY,"
            " name VARCHAR(120),"
            " template_file VARCHAR(300) DEFAULT '',"
            " taxonomy_level VARCHAR(30),"
            " taxonomy_domain VARCHAR(40)"
            ")"
        )
        conn.exec_driver_sql(
            "INSERT INTO item (name, taxonomy_level, taxonomy_domain)"
            " VALUES ('Q1', 'remember', 'cognitive')"
        )
    return eng


def test_metadata():
    mod = _load()
    assert mod.revision == "0004_item_item_type"
    assert mod.base == "global"


def test_upgrade_adds_column(pre_engine):
    _load().upgrade(pre_engine.connect())
    cols = {c["name"] for c in inspect(pre_engine).get_columns("item")}
    assert "item_type" in cols


def test_upgrade_existing_rows_get_null(pre_engine):
    with pre_engine.begin() as conn:
        _load().upgrade(conn)
    with pre_engine.begin() as conn:
        row = conn.execute(
            text("SELECT item_type FROM item WHERE name='Q1'")
        ).one()
    assert row.item_type is None


def test_upgrade_idempotent(pre_engine):
    mod = _load()
    with pre_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_engine.begin() as conn:
        mod.upgrade(conn)
    cols = {c["name"] for c in inspect(pre_engine).get_columns("item")}
    assert "item_type" in cols
