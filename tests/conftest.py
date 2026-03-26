"""Shared test fixtures for WorkFlow test suite."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase, LocalBase


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
