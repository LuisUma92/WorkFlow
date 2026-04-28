"""Tests for workflow.db.cli."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from workflow.db.cli import _project_initials, db
from workflow.db.engine import get_global_engine, init_global_db


@pytest.fixture
def isolated_engine(tmp_path: Path, monkeypatch):
    """Point the CLI at a tmp DB instead of the real XDG path."""
    db_path = tmp_path / "wf.db"
    engine = get_global_engine(db_path=db_path)
    init_global_db(engine)

    def _fake_get_engine(_ctx):
        return engine

    monkeypatch.setattr("workflow.db.cli.get_engine_from_ctx", _fake_get_engine)
    return engine


class TestProjectInitialsValidator:
    def test_accepts_two_uppercase(self):
        assert _project_initials("SF") == "SF"

    def test_uppercases_lowercase(self):
        assert _project_initials("sf") == "SF"

    def test_strips_whitespace(self):
        assert _project_initials("  sf  ") == "SF"

    def test_rejects_digit(self):
        with pytest.raises(click.BadParameter):
            _project_initials("S1")

    def test_rejects_wrong_length(self):
        with pytest.raises(click.BadParameter):
            _project_initials("SFF")


class TestMigrateCli:
    def test_idempotent_run_reports_no_changes(self, isolated_engine):
        runner = CliRunner()
        result = runner.invoke(db, ["migrate", "itep-0008"])
        assert result.exit_code == 0, result.output
        assert "ITEP-0008 migration complete." in result.output
        assert "(no changes — already up to date)" in result.output

    def test_backfill_flag_skips_when_blank_input(self, isolated_engine):
        runner = CliRunner()
        # First prompt is "child code"; blank ends the loop immediately.
        result = runner.invoke(
            db, ["migrate", "itep-0008", "--backfill-nuclear-physics"], input="\n"
        )
        assert result.exit_code == 0, result.output
        assert "areas created:" in result.output
        assert "0060NP" in result.output

    def test_backfill_rejects_invalid_initials(self, isolated_engine):
        runner = CliRunner()
        # child code -> "0060NP25SF", year -> 25, initials -> bad ("S1") then good ("SF")
        result = runner.invoke(
            db,
            ["migrate", "itep-0008", "--backfill-nuclear-physics"],
            input="0060NP25SF\n25\nS1\nSF\nScintillatingFibers\n\n",
        )
        assert result.exit_code == 0, result.output
        assert "must be exactly two uppercase letters" in result.output
