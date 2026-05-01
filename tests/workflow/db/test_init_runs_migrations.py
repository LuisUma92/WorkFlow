"""init_global_db / init_local_db apply migrations on a fresh DB (ITEP-0010)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db, init_local_db, get_global_engine, get_local_engine
from workflow.db.schema_version import current_version


@pytest.fixture
def tmp_global_db(tmp_path: Path):
    db_path = tmp_path / "fresh_global.db"
    return db_path


@pytest.fixture
def tmp_local_db(tmp_path: Path):
    return tmp_path / "fresh_project"


def test_init_global_db_stamps_baseline(tmp_global_db):
    engine = get_global_engine(db_path=tmp_global_db)
    init_global_db(engine=engine)

    insp = inspect(engine)
    assert "schema_version" in insp.get_table_names()
    with Session(engine) as s:
        assert current_version(s, "global") == "0001_baseline"


def test_init_global_db_idempotent(tmp_global_db):
    engine = get_global_engine(db_path=tmp_global_db)
    init_global_db(engine=engine)
    init_global_db(engine=engine)  # should not error

    with Session(engine) as s:
        assert current_version(s, "global") == "0001_baseline"


def test_init_local_db_stamps_baseline(tmp_local_db):
    tmp_local_db.mkdir()
    engine = get_local_engine(tmp_local_db)
    init_local_db(engine=engine)

    insp = inspect(engine)
    assert "schema_version" in insp.get_table_names()
    with Session(engine) as s:
        assert current_version(s, "local") == "0001_baseline"


def test_init_global_db_creates_business_tables_too(tmp_global_db):
    """Existing behavior preserved: model tables still get created."""
    engine = get_global_engine(db_path=tmp_global_db)
    init_global_db(engine=engine)

    insp = inspect(engine)
    names = set(insp.get_table_names())
    # Sample of GlobalBase tables that must still exist after init.
    assert "main_topic" in names
    assert "discipline_area" in names
