"""Tests for workflow exercise list --json / --course / --type filters.

TDD RED → GREEN for Task 1A.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.exercises import Exercise
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.cli import exercise


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def runner():
    return CliRunner()


# ── Fixtures: pre-seeded exercises ──────────────────────────────────────────

COMPLETE_TEX_SSU = """\
% ---
% id: list-test-ssu-001
% type: SSU
% difficulty: medium
% taxonomy_level: Usar-Aplicar
% taxonomy_domain: Procedimiento Mental
% tags: ["CB0009"]
% status: complete
% ---
\\question{What is force?}{F=ma}
"""

COMPLETE_TEX_MULTI = """\
% ---
% id: list-test-mc-001
% type: multichoice
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% tags: ["FS0211"]
% status: complete
% ---
\\question{What is $2+2$?}{$4$}
"""


def _seed_exercise(session: Session, exercise_id: str, ex_type: str, course_tag: str) -> Exercise:
    """Insert a minimal Exercise row directly (bypasses file system)."""
    import hashlib
    ex = Exercise(
        exercise_id=exercise_id,
        source_path=f"/fake/{exercise_id}.tex",
        file_hash=hashlib.sha256(exercise_id.encode()).hexdigest(),
        status="complete",
        type=ex_type,
        difficulty="medium",
        taxonomy_level="Usar-Aplicar",
        taxonomy_domain="Procedimiento Mental",
        tags=json.dumps([course_tag]),
    )
    session.add(ex)
    session.commit()
    return ex


# ── Task 1A: --json flag ─────────────────────────────────────────────────────


class TestListJsonFlag:
    def test_json_flag_exits_zero_empty_db(self, runner, db_engine):
        """--json on empty DB returns [] and exit 0."""
        result = runner.invoke(exercise, ["list", "--json"], obj={"engine": db_engine})
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data == []

    def test_json_flag_returns_valid_json_list(self, runner, db_engine):
        """--json emits a JSON array even when exercises exist."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-json-001", "multichoice", "CB0009")

        result = runner.invoke(exercise, ["list", "--json"], obj={"engine": db_engine})
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_json_keys_minimum_required(self, runner, db_engine):
        """Each JSON object contains at minimum id, file, type, course keys."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-json-002", "essay", "FS0211")

        result = runner.invoke(exercise, ["list", "--json"], obj={"engine": db_engine})
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        obj = data[0]
        for key in ("id", "file", "type", "course"):
            assert key in obj, f"Missing key: {key}"

    def test_json_id_field_matches_exercise_id(self, runner, db_engine):
        """JSON 'id' field matches exercise_id."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-json-003", "multichoice", "CB0009")

        result = runner.invoke(exercise, ["list", "--json"], obj={"engine": db_engine})
        data = json.loads(result.output)
        assert data[0]["id"] == "list-json-003"

    def test_json_file_field_present(self, runner, db_engine):
        """JSON 'file' field is populated (source_path)."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-json-004", "essay", "CB0009")

        result = runner.invoke(exercise, ["list", "--json"], obj={"engine": db_engine})
        data = json.loads(result.output)
        assert data[0]["file"] is not None


# ── Task 1A: --course filter ─────────────────────────────────────────────────


class TestListFilterCourse:
    def test_course_filter_returns_matching_only(self, runner, db_engine):
        """--course CB0009 returns only exercises tagged CB0009."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-course-001", "SSU", "CB0009")
            _seed_exercise(s, "list-course-002", "multichoice", "FS0211")

        result = runner.invoke(
            exercise, ["list", "--course", "CB0009", "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        ids = [d["id"] for d in data]
        assert "list-course-001" in ids
        assert "list-course-002" not in ids

    def test_course_filter_empty_result_exits_zero(self, runner, db_engine):
        """--course with no matching exercises returns [] with exit 0."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-course-003", "essay", "FS0211")

        result = runner.invoke(
            exercise, ["list", "--course", "CB0009", "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data == []

    def test_course_field_in_json_output(self, runner, db_engine):
        """The 'course' field in JSON output matches the requested course."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-course-004", "SSU", "CB0009")

        result = runner.invoke(
            exercise, ["list", "--course", "CB0009", "--json"], obj={"engine": db_engine}
        )
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["course"] == "CB0009"


# ── Task 1A: --type filter extended (SCM/SSU/SDE) ───────────────────────────


class TestListFilterType:
    def test_type_filter_ssu(self, runner, db_engine):
        """--type SSU returns only SSU exercises."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-type-ssu-001", "SSU", "CB0009")
            _seed_exercise(s, "list-type-mc-001", "multichoice", "CB0009")

        result = runner.invoke(
            exercise, ["list", "--type", "SSU", "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert all(d["type"] == "SSU" for d in data)
        ids = [d["id"] for d in data]
        assert "list-type-ssu-001" in ids
        assert "list-type-mc-001" not in ids

    def test_type_filter_scm(self, runner, db_engine):
        """--type SCM is accepted and filters correctly."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-type-scm-001", "SCM", "CB0009")

        result = runner.invoke(
            exercise, ["list", "--type", "SCM", "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["type"] == "SCM"

    def test_type_filter_sde(self, runner, db_engine):
        """--type SDE is accepted and filters correctly."""
        with Session(db_engine) as s:
            _seed_exercise(s, "list-type-sde-001", "SDE", "CB0009")

        result = runner.invoke(
            exercise, ["list", "--type", "SDE", "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["type"] == "SDE"
