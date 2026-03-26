"""Tests for workflow.db.engine — engine and DB initialisation."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from workflow.db.engine import (
    get_global_engine,
    get_local_engine,
    init_global_db,
    init_local_db,
)


class TestGetGlobalEngine:
    def test_get_global_engine_returns_engine(self, tmp_path: Path) -> None:
        """get_global_engine returns a SQLAlchemy Engine."""
        db_path = tmp_path / "test_global.db"
        engine = get_global_engine(db_path=db_path)
        assert isinstance(engine, Engine)

    def test_get_global_engine_creates_parent_dirs(self, tmp_path: Path) -> None:
        """get_global_engine creates parent directories if missing."""
        db_path = tmp_path / "nested" / "dir" / "workflow.db"
        engine = get_global_engine(db_path=db_path)
        assert db_path.parent.exists()
        assert isinstance(engine, Engine)


class TestGetLocalEngine:
    def test_get_local_engine_returns_engine(self, tmp_path: Path) -> None:
        """get_local_engine returns a SQLAlchemy Engine."""
        engine = get_local_engine(project_root=tmp_path)
        assert isinstance(engine, Engine)

    def test_get_local_engine_uses_slipbox_db(self, tmp_path: Path) -> None:
        """get_local_engine points to <project_root>/slipbox.db."""
        engine = get_local_engine(project_root=tmp_path)
        url = str(engine.url)
        assert "slipbox.db" in url


class TestInitGlobalDb:
    def test_init_global_db_creates_tables(self, tmp_path: Path) -> None:
        """init_global_db creates tables without error."""
        db_path = tmp_path / "global.db"
        engine = get_global_engine(db_path=db_path)
        result = init_global_db(engine=engine)
        assert result is engine

    def test_init_global_db_idempotent(self, tmp_path: Path) -> None:
        """Calling init_global_db twice does not raise."""
        db_path = tmp_path / "global.db"
        engine = get_global_engine(db_path=db_path)
        init_global_db(engine=engine)
        init_global_db(engine=engine)  # second call must not raise


class TestInitLocalDb:
    def test_init_local_db_creates_tables(self, tmp_path: Path) -> None:
        """init_local_db creates local tables without error."""
        engine = get_local_engine(project_root=tmp_path)
        result = init_local_db(engine=engine)
        assert result is engine

    def test_init_local_db_via_project_root(self, tmp_path: Path) -> None:
        """init_local_db accepts project_root instead of engine."""
        result = init_local_db(project_root=tmp_path)
        assert isinstance(result, Engine)
        db_path = tmp_path / "slipbox.db"
        assert db_path.exists()
