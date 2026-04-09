"""Tests for evaluation CLI commands (evaluations, item, course)."""

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.academic import (
    Course,
    EvaluationItem,
    EvaluationTemplate,
    Institution,
    Item,
)
from workflow.evaluation.cli import course, evaluations, item


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
    """Engine with institutions, templates, items, courses seeded."""
    with Session(engine) as session:
        ucr = Institution(
            short_name="UCR", full_name="Universidad de Costa Rica",
            cycle_weeks=16, cycle_name="Semestre",
        )
        ufide = Institution(
            short_name="UFide", full_name="Universidad Fidélitas",
            cycle_weeks=15, cycle_name="Cuatrimestre",
        )
        session.add_all([ucr, ufide])
        session.flush()

        tmpl = EvaluationTemplate(
            institution_id=ufide.id, name="Estudio de caso",
        )
        session.add(tmpl)
        session.flush()

        it1 = Item(
            name="SU - Info/Recordar",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        it2 = Item(
            name="Desarrollo - Proc. Mental/Aplicar",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
        )
        session.add_all([it1, it2])
        session.flush()

        session.add(EvaluationItem(
            evaluation_id=tmpl.id, item_id=it1.id,
            total_amount=2, points_per_item=5,
        ))
        session.add(EvaluationItem(
            evaluation_id=tmpl.id, item_id=it2.id,
            total_amount=1, points_per_item=16,
        ))

        session.add(Course(
            institution_id=ucr.id, code="FI-201", name="Física II",
        ))
        session.commit()
    return engine


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, cmd, args, engine):
    return runner.invoke(cmd, args, obj={"engine": engine}, catch_exceptions=False)


class TestEvaluationsList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, evaluations, ["list"], engine)
        assert result.exit_code == 0
        assert "No evaluation templates found" in result.output

    def test_list_shows_templates(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["list"], seeded_engine)
        assert result.exit_code == 0
        assert "Estudio de caso" in result.output
        assert "UFide" in result.output

    def test_list_filter_by_inst(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["list", "--inst", "UCR"], seeded_engine)
        assert result.exit_code == 0
        assert "No evaluation templates found" in result.output

    def test_list_full(self, runner, seeded_engine):
        result = _invoke(
            runner, evaluations, ["list", "--full"], seeded_engine,
        )
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output
        assert "2 × 5 pts" in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(
            runner, evaluations, ["list", "--json"], seeded_engine,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "Estudio de caso"

    def test_list_json_full(self, runner, seeded_engine):
        result = _invoke(
            runner, evaluations, ["list", "--json", "--full"], seeded_engine,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "items" in data[0]
        assert len(data[0]["items"]) == 2


class TestItemList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, item, ["list"], engine)
        assert result.exit_code == 0
        assert "No items found" in result.output

    def test_list_shows_items(self, runner, seeded_engine):
        result = _invoke(runner, item, ["list"], seeded_engine)
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output

    def test_list_filter_by_domain(self, runner, seeded_engine):
        result = _invoke(
            runner, item, ["list", "--domain", "Información"], seeded_engine,
        )
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output
        assert "Proc. Mental" not in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(runner, item, ["list", "--json"], seeded_engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2


class TestCourseList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, course, ["list"], engine)
        assert result.exit_code == 0
        assert "No courses found" in result.output

    def test_list_shows_courses(self, runner, seeded_engine):
        result = _invoke(runner, course, ["list"], seeded_engine)
        assert result.exit_code == 0
        assert "FI-201" in result.output
        assert "Física II" in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(runner, course, ["list", "--json"], seeded_engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["code"] == "FI-201"
