"""Tests for `workflow project list` / `workflow project adopt` (ITEP-0008 P0).

Also covers the dirname parser `itep.naming.parse_project_dirname`, written
here per the plan since the parser has no existing test module.
"""

from __future__ import annotations

import json
import os
import time

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from itep.naming import ParsedProjectName, parse_project_dirname
from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.project import GeneralProject
from workflow.project.cli import project


# ── Parser tests ────────────────────────────────────────────────────────


class TestParseProjectDirname:
    def test_valid_name(self):
        parsed = parse_project_dirname("0060NP-23BP-BerylliumProcess")
        assert parsed == ParsedProjectName(
            area_code="0060NP",
            year_init=23,
            project_initials="BP",
            title="BerylliumProcess",
        )

    def test_valid_name_other(self):
        parsed = parse_project_dirname("0060NP-26RC-ReporteCERN")
        assert parsed.area_code == "0060NP"
        assert parsed.year_init == 26
        assert parsed.project_initials == "RC"
        assert parsed.title == "ReporteCERN"

    def test_rejects_two_digit_area_legacy_scheme(self):
        assert parse_project_dirname("60NP-23BP-x") is None

    def test_rejects_four_digit_year(self):
        assert parse_project_dirname("0060NP-2023BP-x") is None

    def test_rejects_lowercase(self):
        assert parse_project_dirname("0060np-23bp-x") is None

    def test_rejects_no_hyphens(self):
        assert parse_project_dirname("0060NP23BPx") is None

    def test_rejects_empty_title(self):
        assert parse_project_dirname("0060NP-23BP-") is None

    def test_rejects_one_letter_initials(self):
        assert parse_project_dirname("0060NP-23B-Title") is None


# ── CLI fixtures ─────────────────────────────────────────────────────────


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture
def seeded_engine(engine):
    """Engine with a 0060NP DisciplineArea seeded."""
    with Session(engine) as session:
        session.add(
            DisciplineArea(
                code="0060NP",
                name="Nuclear Physics",
                dewey="539.7",
                discipline_num=0,
                topic_num=60,
                area_initials="NP",
            )
        )
        session.commit()
    return engine


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, cmd, args, engine):
    return runner.invoke(cmd, args, obj={"engine": engine}, catch_exceptions=False)


@pytest.fixture
def repo_dir(tmp_path):
    """A directory named per ADR ITEP-0008, with pre-existing content."""
    d = tmp_path / "0060NP-23BP-BerylliumProcess"
    d.mkdir()
    (d / "README.md").write_text("hello\n")
    (d / ".git").mkdir()
    return d


# ── `project adopt` ────────────────────────────────────────────────────


class TestProjectAdopt:
    def test_adopt_inserts_main_topic_and_general_project(
        self, runner, seeded_engine, repo_dir
    ):
        result = _invoke(runner, project, ["adopt", str(repo_dir)], seeded_engine)
        assert result.exit_code == 0, result.output

        with Session(seeded_engine) as session:
            mt = session.query(MainTopic).filter_by(code="0060NP23BP").first()
            assert mt is not None
            assert mt.name == "BerylliumProcess"

            gp = session.query(GeneralProject).filter_by(main_topic_id=mt.id).first()
            assert gp is not None
            assert gp.year_init == 23
            assert gp.project_initials == "BP"
            assert gp.title == "BerylliumProcess"
            assert gp.status == "active"
            assert gp.abs_parent_dir == str(repo_dir.parent)

    def test_adopt_json_created_true(self, runner, seeded_engine, repo_dir):
        result = _invoke(
            runner, project, ["adopt", str(repo_dir), "--json"], seeded_engine
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["main_topic_code"] == "0060NP23BP"

    def test_adopt_does_not_touch_directory_contents(
        self, runner, seeded_engine, repo_dir
    ):
        readme = repo_dir / "README.md"
        before_content = readme.read_text()
        before_mtime = readme.stat().st_mtime

        time.sleep(0.01)
        _invoke(runner, project, ["adopt", str(repo_dir)], seeded_engine)

        assert readme.read_text() == before_content
        assert readme.stat().st_mtime == before_mtime
        # No ITeP scaffolding created.
        assert not (repo_dir / "bib").exists()
        assert not (repo_dir / "tex").exists()
        assert not (repo_dir / "config.yaml").exists()
        # Only the two pre-existing entries remain.
        assert set(os.listdir(repo_dir)) == {"README.md", ".git"}

    def test_adopt_twice_is_idempotent(self, runner, seeded_engine, repo_dir):
        first = _invoke(runner, project, ["adopt", str(repo_dir)], seeded_engine)
        assert first.exit_code == 0

        second = _invoke(
            runner, project, ["adopt", str(repo_dir), "--json"], seeded_engine
        )
        assert second.exit_code == 0, second.output
        data = json.loads(second.output)
        assert data["created"] is False

        with Session(seeded_engine) as session:
            rows = (
                session.query(GeneralProject)
                .join(MainTopic, GeneralProject.main_topic_id == MainTopic.id)
                .filter(MainTopic.code == "0060NP23BP")
                .all()
            )
            assert len(rows) == 1

    def test_adopt_malformed_name_exits_1(self, runner, seeded_engine, tmp_path):
        bad_dir = tmp_path / "not-a-valid-name"
        bad_dir.mkdir()
        result = _invoke(runner, project, ["adopt", str(bad_dir)], seeded_engine)
        assert result.exit_code == 1

    def test_adopt_nonexistent_path_exits_2(self, runner, seeded_engine, tmp_path):
        missing = tmp_path / "0060NP-23BP-Missing"
        result = _invoke(runner, project, ["adopt", str(missing)], seeded_engine)
        assert result.exit_code == 2

    def test_adopt_path_is_a_file_exits_2(self, runner, seeded_engine, tmp_path):
        f = tmp_path / "0060NP-23BP-NotADir"
        f.write_text("x")
        result = _invoke(runner, project, ["adopt", str(f)], seeded_engine)
        assert result.exit_code == 2

    def test_adopt_dry_run_writes_nothing(self, runner, seeded_engine, repo_dir):
        result = _invoke(
            runner, project, ["adopt", str(repo_dir), "--dry-run", "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["created"] is False
        assert data["dry_run"] is True

        with Session(seeded_engine) as session:
            assert session.query(MainTopic).filter_by(code="0060NP23BP").first() is None
            assert session.query(GeneralProject).count() == 0

    def test_adopt_unknown_discipline_area_errors(self, runner, engine, tmp_path):
        # `engine` has NO DisciplineArea seeded.
        d = tmp_path / "0060NP-23BP-BerylliumProcess"
        d.mkdir()
        result = _invoke(runner, project, ["adopt", str(d)], engine)
        assert result.exit_code == 1
        assert "0060NP" in result.output


# ── `project list` ─────────────────────────────────────────────────────


class TestProjectList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, project, ["list"], engine)
        assert result.exit_code == 0
        assert "No projects found" in result.output

    def test_list_shows_adopted_project(self, runner, seeded_engine, repo_dir):
        _invoke(runner, project, ["adopt", str(repo_dir)], seeded_engine)
        result = _invoke(runner, project, ["list"], seeded_engine)
        assert result.exit_code == 0
        assert "0060NP23BP" in result.output
        assert "BerylliumProcess" in result.output

    def test_list_json_parseable(self, runner, seeded_engine, repo_dir):
        _invoke(runner, project, ["adopt", str(repo_dir)], seeded_engine)
        result = _invoke(runner, project, ["list", "--json"], seeded_engine)
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["code"] == "0060NP23BP"
        assert data[0]["title"] == "BerylliumProcess"
        assert data[0]["year_init"] == 23
        assert data[0]["project_initials"] == "BP"
        assert data[0]["status"] == "active"
        assert data[0]["abs_parent_dir"] == str(repo_dir.parent)
