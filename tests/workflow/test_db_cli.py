"""Tests for workflow.db.cli (post-ITEP-0010)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from workflow.db.cli import db
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


class TestImportCodesCli:
    def _write_csv(self, path: Path, body: str) -> Path:
        path.write_text("Rama,código,Dewey\n" + body, encoding="utf-8")
        return path

    def test_requires_csv_or_all(self, isolated_engine):
        runner = CliRunner()
        result = runner.invoke(db, ["import-codes"])
        assert result.exit_code != 0
        assert "specify --csv PATH or --all" in result.output

    def test_rejects_both_flags(self, isolated_engine, tmp_path):
        csv = self._write_csv(tmp_path / "00-PhysicsCodes.csv", "Mec,10MC,\n")
        runner = CliRunner()
        result = runner.invoke(db, ["import-codes", "--csv", str(csv), "--all"])
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_imports_single_csv(self, isolated_engine, tmp_path):
        csv = self._write_csv(
            tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-00\n"
        )
        runner = CliRunner()
        result = runner.invoke(db, ["import-codes", "--csv", str(csv)])
        assert result.exit_code == 0, result.output
        assert "inserted" in result.output
        assert "0010MC" in result.output

    def test_imports_all_with_data_dir(self, isolated_engine, tmp_path):
        self._write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,\n")
        self._write_csv(tmp_path / "01-PhilosophyCodes.csv", "Lógica,10LO,\n")
        runner = CliRunner()
        result = runner.invoke(
            db, ["import-codes", "--all", "--data-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert "0010MC" in result.output
        assert "0110LO" in result.output

    def test_idempotent_second_run(self, isolated_engine, tmp_path):
        csv = self._write_csv(tmp_path / "00-PhysicsCodes.csv", "Mec,10MC,\n")
        runner = CliRunner()
        runner.invoke(db, ["import-codes", "--csv", str(csv)])
        result = runner.invoke(db, ["import-codes", "--csv", str(csv)])
        assert result.exit_code == 0, result.output
        assert "(no changes — already up to date)" in result.output
