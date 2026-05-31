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


class TestDisciplineAreasListCli:
    def _seed(self, engine, rows):
        from sqlalchemy.orm import Session as _Session
        from workflow.db.models.knowledge import DisciplineArea
        with _Session(engine) as s:
            s.add_all([DisciplineArea(**r) for r in rows])
            s.commit()

    _MC = {"code": "0010MC", "name": "Mecánica Clásica", "discipline_num": 0,
           "topic_num": 10, "area_initials": "MC"}
    _PG = {"code": "0210PG", "name": "Programación", "discipline_num": 2,
           "topic_num": 10, "area_initials": "PG"}

    def test_empty_table(self, isolated_engine):
        result = CliRunner().invoke(db, ["discipline-areas", "list"])
        assert result.exit_code == 0, result.output
        assert "No discipline areas found" in result.output

    def test_empty_json(self, isolated_engine):
        import json
        result = CliRunner().invoke(db, ["discipline-areas", "list", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == []

    def test_table_shows_rows_sorted(self, isolated_engine):
        self._seed(isolated_engine, [self._PG, self._MC])
        result = CliRunner().invoke(db, ["discipline-areas", "list"])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "0010MC" in out
        assert "Mecánica Clásica" in out
        assert "0210PG" in out
        assert out.index("0010MC") < out.index("0210PG")

    def test_json_shape(self, isolated_engine):
        import json
        self._seed(isolated_engine, [self._MC])
        result = CliRunner().invoke(db, ["discipline-areas", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        row = data[0]
        assert row == {"code": "0010MC", "discipline_num": 0,
                       "name": "Mecánica Clásica", "area_initials": "MC"}

    def test_dd_filter(self, isolated_engine):
        self._seed(isolated_engine, [self._MC, self._PG])
        result = CliRunner().invoke(db, ["discipline-areas", "list", "--dd", "00"])
        assert result.exit_code == 0, result.output
        assert "0010MC" in result.output
        assert "0210PG" not in result.output

    def test_dd_unknown_prefix_empty(self, isolated_engine):
        self._seed(isolated_engine, [self._MC])
        result = CliRunner().invoke(db, ["discipline-areas", "list", "--dd", "99"])
        assert result.exit_code == 0, result.output
        assert "No discipline areas found" in result.output

    def test_dd_malformed(self, isolated_engine):
        result = CliRunner().invoke(db, ["discipline-areas", "list", "--dd", "xx"])
        assert result.exit_code != 0
