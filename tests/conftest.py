"""Shared test fixtures for WorkFlow test suite."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase, LocalBase


@pytest.fixture(autouse=True)
def _isolate_workflow_data_dir(tmp_path_factory, monkeypatch):
    """Point WORKFLOW_DATA_DIR at a per-test temp dir.

    CLI commands resolve the global DB via ``WORKFLOW_DATA_DIR`` (default
    ``~/01-U/workflow/workflow.db`` — the LIVE database). Without this, any test
    that invokes a Click command and falls through to ``get_global_engine()``
    reads/writes the real vault DB, which both pollutes results and lets real
    data trip FK constraints. This autouse fixture guarantees every test gets a
    fresh, isolated, empty global DB (tables are created on first engine init).

    Tests that need a specific data dir still override it (their own
    ``monkeypatch.setenv`` runs after this fixture and wins).
    """
    data_dir = tmp_path_factory.mktemp("workflow_data")
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(data_dir))


def _enable_fk(dbapi_conn, _connection_record):
    """Enable SQLite foreign key enforcement."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def global_engine():
    """In-memory SQLite engine for GlobalBase tables."""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def global_session(global_engine):
    """Session for GlobalBase in-memory DB."""
    with Session(global_engine) as session:
        yield session


@pytest.fixture
def local_engine():
    """In-memory SQLite engine for LocalBase tables."""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    LocalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def local_session(local_engine):
    """Session for LocalBase in-memory DB."""
    with Session(local_engine) as session:
        yield session
