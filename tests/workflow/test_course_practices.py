"""Tests for course add-practice and practices CLI commands.

Acceptance criteria from tasks/requests/2026-04-29-course-add-practice-quiz.md:
  - register: inserts row in course_evaluation
  - list: practices listed ordered by type, serial
  - collision: serial collision exits 1 with 'already registered'
  - auto-serial: omitting --serial assigns next available integer
  - unknown-course: exits 1 with 'course not found'
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.academic import Course, CourseEvaluation, Institution
from workflow.evaluation.cli import course


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
    """Engine with UCR institution and FS0211 course seeded."""
    with Session(engine) as session:
        ucr = Institution(
            short_name="UCR",
            full_name="Universidad de Costa Rica",
            cycle_weeks=16,
            cycle_name="Semestre",
        )
        session.add(ucr)
        session.flush()

        c = Course(
            institution_id=ucr.id,
            code="FS0211",
            name="Física II",
        )
        session.add(c)
        session.commit()
    return engine


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, cmd, args, engine):
    return runner.invoke(cmd, args, obj={"engine": engine}, catch_exceptions=False)


# ── register ─────────────────────────────────────────────────────────────


class TestCourseAddPractice:
    def test_register_quiz(self, runner, seeded_engine):
        """add-practice inserts a row in course_evaluation."""
        result = _invoke(
            runner,
            course,
            [
                "add-practice",
                "FS0211",
                "--name", "Cinemática I",
                "--week", "2",
                "--type", "quiz",
                "--serial", "1",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output
        assert "quiz" in result.output
        assert "FS0211" in result.output

        with Session(seeded_engine) as session:
            rows = session.query(CourseEvaluation).all()
        assert len(rows) == 1
        assert rows[0].practice_type == "quiz"
        assert rows[0].serial_number == 1
        assert rows[0].practice_name == "Cinemática I"

    def test_register_practice(self, runner, seeded_engine):
        """add-practice works with type=practice."""
        result = _invoke(
            runner,
            course,
            [
                "add-practice",
                "FS0211",
                "--name", "Lab I",
                "--week", "3",
                "--type", "practice",
                "--serial", "1",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output

    def test_register_with_file(self, runner, seeded_engine):
        """--file stores the source path."""
        result = _invoke(
            runner,
            course,
            [
                "add-practice",
                "FS0211",
                "--name", "PC01",
                "--week", "2",
                "--type", "quiz",
                "--serial", "1",
                "--file", "eval/PC01.xml",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output

        with Session(seeded_engine) as session:
            row = session.query(CourseEvaluation).first()
        assert row.source_file == "eval/PC01.xml"

    def test_register_json_output(self, runner, seeded_engine):
        """--json returns correct shape."""
        result = _invoke(
            runner,
            course,
            [
                "add-practice",
                "FS0211",
                "--name", "Leyes del Movimiento II",
                "--week", "6",
                "--type", "quiz",
                "--serial", "4",
                "--file", "eval/PC04.xml",
                "--json",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["course"] == "FS0211"
        assert data["type"] == "quiz"
        assert data["serial"] == 4
        assert data["name"] == "Leyes del Movimiento II"
        assert data["week"] == 6
        assert data["file"] == "eval/PC04.xml"
        assert "id" in data


# ── list ──────────────────────────────────────────────────────────────────


class TestCoursePracticesList:
    def _register(self, runner, engine, course_code, name, week, ptype, serial, file=None):
        args = [
            "add-practice", course_code,
            "--name", name,
            "--week", str(week),
            "--type", ptype,
            "--serial", str(serial),
        ]
        if file:
            args += ["--file", file]
        return _invoke(runner, course, args, engine)

    def test_list_empty(self, runner, seeded_engine):
        result = _invoke(runner, course, ["practices", "FS0211"], seeded_engine)
        assert result.exit_code == 0
        assert "No practices" in result.output

    def test_list_two_entries(self, runner, seeded_engine):
        self._register(runner, seeded_engine, "FS0211", "PC01", 2, "quiz", 1)
        self._register(runner, seeded_engine, "FS0211", "Lab I", 3, "practice", 1)

        result = _invoke(runner, course, ["practices", "FS0211", "--json"], seeded_engine)
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 2

    def test_list_json_fields(self, runner, seeded_engine):
        self._register(runner, seeded_engine, "FS0211", "PC01", 2, "quiz", 1, "eval/PC01.xml")

        result = _invoke(runner, course, ["practices", "FS0211", "--json"], seeded_engine)
        data = json.loads(result.output)
        entry = data[0]
        assert set(entry.keys()) >= {"id", "course", "type", "serial", "name", "week", "file"}
        assert entry["course"] == "FS0211"
        assert entry["type"] == "quiz"
        assert entry["serial"] == 1
        assert entry["file"] == "eval/PC01.xml"

    def test_list_ordered_by_type_then_serial(self, runner, seeded_engine):
        """Practices ordered by type then serial."""
        self._register(runner, seeded_engine, "FS0211", "PC03", 5, "quiz", 3)
        self._register(runner, seeded_engine, "FS0211", "PC01", 2, "quiz", 1)
        self._register(runner, seeded_engine, "FS0211", "Lab II", 4, "practice", 2)
        self._register(runner, seeded_engine, "FS0211", "Lab I", 3, "practice", 1)

        result = _invoke(runner, course, ["practices", "FS0211", "--json"], seeded_engine)
        data = json.loads(result.output)
        assert len(data) == 4
        # practice < quiz alphabetically
        assert data[0]["type"] == "practice" and data[0]["serial"] == 1
        assert data[1]["type"] == "practice" and data[1]["serial"] == 2
        assert data[2]["type"] == "quiz" and data[2]["serial"] == 1
        assert data[3]["type"] == "quiz" and data[3]["serial"] == 3


# ── collision ─────────────────────────────────────────────────────────────


class TestSerialCollision:
    def test_collision_exits_1(self, runner, seeded_engine):
        """Registering the same serial twice exits 1."""
        _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC01", "--week", "2",
             "--type", "quiz", "--serial", "1"],
            seeded_engine,
        )
        result = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC01 dup", "--week", "2",
             "--type", "quiz", "--serial", "1"],
            seeded_engine,
        )
        assert result.exit_code != 0
        assert "already registered" in result.output

    def test_collision_message_contains_serial_and_course(self, runner, seeded_engine):
        _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC04", "--week", "6",
             "--type", "quiz", "--serial", "4"],
            seeded_engine,
        )
        result = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "Another PC04", "--week", "6",
             "--type", "quiz", "--serial", "4"],
            seeded_engine,
        )
        assert result.exit_code != 0
        assert "4" in result.output
        assert "FS0211" in result.output

    def test_same_serial_different_type_ok(self, runner, seeded_engine):
        """Serial 1 for quiz and serial 1 for practice do NOT collide."""
        r1 = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC01", "--week", "2",
             "--type", "quiz", "--serial", "1"],
            seeded_engine,
        )
        r2 = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "Lab I", "--week", "3",
             "--type", "practice", "--serial", "1"],
            seeded_engine,
        )
        assert r1.exit_code == 0
        assert r2.exit_code == 0


# ── auto-serial ───────────────────────────────────────────────────────────


class TestAutoSerial:
    def test_auto_serial_first_entry(self, runner, seeded_engine):
        """With no existing entries, auto-serial assigns 1."""
        result = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC01", "--week", "2",
             "--type", "quiz", "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["serial"] == 1

    def test_auto_serial_increments(self, runner, seeded_engine):
        """Auto-serial increments from the current max for that (course, type)."""
        _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC01", "--week", "2",
             "--type", "quiz", "--serial", "3"],
            seeded_engine,
        )
        result = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC02", "--week", "4",
             "--type", "quiz", "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["serial"] == 4

    def test_auto_serial_independent_per_type(self, runner, seeded_engine):
        """Auto-serial tracks per (course, type) pair independently."""
        _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "PC01", "--week", "2",
             "--type", "quiz", "--serial", "5"],
            seeded_engine,
        )
        result = _invoke(
            runner,
            course,
            ["add-practice", "FS0211", "--name", "Lab I", "--week", "3",
             "--type", "practice", "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["serial"] == 1  # independent from quiz series


# ── unknown course ────────────────────────────────────────────────────────


class TestUnknownCourse:
    def test_add_practice_unknown_course(self, runner, seeded_engine):
        result = _invoke(
            runner,
            course,
            ["add-practice", "XX9999", "--name", "Test", "--week", "1",
             "--type", "quiz"],
            seeded_engine,
        )
        assert result.exit_code != 0
        assert "course not found" in result.output

    def test_practices_list_unknown_course(self, runner, seeded_engine):
        result = _invoke(runner, course, ["practices", "NOPE"], seeded_engine)
        assert result.exit_code != 0
        assert "course not found" in result.output
