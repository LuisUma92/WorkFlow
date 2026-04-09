"""Tests for evaluation CLI commands (evaluations, item, course)."""

import json
import re

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
            short_name="UCR",
            full_name="Universidad de Costa Rica",
            cycle_weeks=16,
            cycle_name="Semestre",
        )
        ufide = Institution(
            short_name="UFide",
            full_name="Universidad Fidélitas",
            cycle_weeks=15,
            cycle_name="Cuatrimestre",
        )
        session.add_all([ucr, ufide])
        session.flush()

        tmpl = EvaluationTemplate(
            institution_id=ufide.id,
            name="Estudio de caso",
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

        session.add(
            EvaluationItem(
                evaluation_id=tmpl.id,
                item_id=it1.id,
                total_amount=2,
                points_per_item=5,
            )
        )
        session.add(
            EvaluationItem(
                evaluation_id=tmpl.id,
                item_id=it2.id,
                total_amount=1,
                points_per_item=16,
            )
        )

        session.add(
            Course(
                institution_id=ucr.id,
                code="FI-201",
                name="Física II",
            )
        )
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
            runner,
            evaluations,
            ["list", "--full"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output
        assert "2 × 5 pts" in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(
            runner,
            evaluations,
            ["list", "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "Estudio de caso"

    def test_list_json_full(self, runner, seeded_engine):
        result = _invoke(
            runner,
            evaluations,
            ["list", "--json", "--full"],
            seeded_engine,
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
            runner,
            item,
            ["list", "--domain", "Información"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output
        assert "Proc. Mental" not in result.output

    def test_list_filter_by_level(self, runner, seeded_engine):
        result = _invoke(
            runner,
            item,
            ["list", "--level", "Recordar"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output
        assert "Usar-Aplicar" not in result.output

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

    def test_list_filter_by_inst(self, runner, seeded_engine):
        result = _invoke(runner, course, ["list", "--inst", "UCR"], seeded_engine)
        assert result.exit_code == 0
        assert "FI-201" in result.output

    def test_list_filter_by_inst_no_match(self, runner, seeded_engine):
        result = _invoke(runner, course, ["list", "--inst", "UFide"], seeded_engine)
        assert result.exit_code == 0
        assert "No courses found" in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(runner, course, ["list", "--json"], seeded_engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["code"] == "FI-201"


# ── P1: Add command tests ────────────────────────────────────────────────


class TestItemAdd:
    def test_add_item_basic(self, runner, seeded_engine):
        result = _invoke(
            runner,
            item,
            [
                "add",
                "--name",
                "SU - Info/Recordar",
                "--level",
                "Recordar",
                "--domain",
                "Información",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Created item" in result.output

    def test_add_item_with_type(self, runner, seeded_engine):
        result = _invoke(
            runner,
            item,
            [
                "add",
                "--name",
                "SU - Info/Recordar",
                "--level",
                "Recordar",
                "--domain",
                "Información",
                "--item-type",
                "SU",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0

    def test_add_item_invalid_level(self, runner, seeded_engine):
        result = _invoke(
            runner,
            item,
            [
                "add",
                "--name",
                "Bad",
                "--level",
                "Inventado",
                "--domain",
                "Información",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_add_item_shows_in_list(self, runner, seeded_engine):
        _invoke(
            runner,
            item,
            [
                "add",
                "--name",
                "NewItem",
                "--level",
                "Comprender",
                "--domain",
                "Información",
            ],
            seeded_engine,
        )
        result = _invoke(runner, item, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        names = [d["name"] for d in data]
        assert "NewItem" in names


class TestEvaluationsAdd:
    def test_add_template_basic(self, runner, seeded_engine):
        result = _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "UFide",
                "--name",
                "Prueba parcial",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_add_template_with_description(self, runner, seeded_engine):
        result = _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "UCR",
                "--name",
                "Parcial 1",
                "--description",
                "Primera evaluación parcial.",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0

    def test_add_template_shows_in_list(self, runner, seeded_engine):
        _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "UCR",
                "--name",
                "Parcial nuevo",
            ],
            seeded_engine,
        )
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        names = [d["name"] for d in data]
        assert "Parcial nuevo" in names

    def test_add_template_duplicate_fails(self, runner, seeded_engine):
        """Estudio de caso already exists for UFide in seed data."""
        result = _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "UFide",
                "--name",
                "Estudio de caso",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_add_template_invalid_institution(self, runner, seeded_engine):
        result = _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "NONEXIST",
                "--name",
                "Test",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0


# ── P2: course add ───────────────────────────────────────────────────────


class TestCourseAdd:
    def test_add_course_basic(self, runner, seeded_engine):
        result = _invoke(
            runner,
            course,
            [
                "add",
                "--inst",
                "UCR",
                "--code",
                "MA-101",
                "--name",
                "Cálculo I",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Created course" in result.output

    def test_add_course_with_schedule(self, runner, seeded_engine):
        result = _invoke(
            runner,
            course,
            [
                "add",
                "--inst",
                "UFide",
                "--code",
                "FI-301",
                "--name",
                "Física III",
                "--lpw",
                "4",
                "--hpl",
                "1",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0

    def test_add_course_shows_in_list(self, runner, seeded_engine):
        _invoke(
            runner,
            course,
            [
                "add",
                "--inst",
                "UCR",
                "--code",
                "QU-100",
                "--name",
                "Química General",
            ],
            seeded_engine,
        )
        result = _invoke(runner, course, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        codes = [d["code"] for d in data]
        assert "QU-100" in codes

    def test_add_course_duplicate_fails(self, runner, seeded_engine):
        """FI-201 already exists for UCR in seed data."""
        result = _invoke(
            runner,
            course,
            [
                "add",
                "--inst",
                "UCR",
                "--code",
                "FI-201",
                "--name",
                "Duplicate",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_add_course_invalid_institution(self, runner, seeded_engine):
        result = _invoke(
            runner,
            course,
            [
                "add",
                "--inst",
                "NONEXIST",
                "--code",
                "X-1",
                "--name",
                "Test",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0


# ── P2: evaluations edit ─────────────────────────────────────────────────


class TestEvaluationsEdit:
    def test_rename_template(self, runner, seeded_engine):
        # Get the template id first
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        tmpl_id = str(data[0]["id"])

        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "rename",
                "--name",
                "Nuevo nombre",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Renamed" in result.output

    def test_rename_shows_in_list(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        tmpl_id = str(data[0]["id"])

        _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "rename",
                "--name",
                "Renamed template",
            ],
            seeded_engine,
        )

        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        names = [d["name"] for d in data]
        assert "Renamed template" in names

    def test_add_item_to_template(self, runner, seeded_engine):
        # Get template and item ids
        tmpl_result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        tmpl_id = str(json.loads(tmpl_result.output)[0]["id"])

        item_result = _invoke(runner, item, ["list", "--json"], seeded_engine)
        item_id = str(json.loads(item_result.output)[0]["id"])

        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "add-item",
                "--item-id",
                item_id,
                "--amount",
                "3",
                "--points",
                "10",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Added item" in result.output

    def test_remove_item_from_template(self, runner, seeded_engine):
        # Get the full template to find an evaluation_item id
        tmpl_result = _invoke(
            runner,
            evaluations,
            ["list", "--json", "--full"],
            seeded_engine,
        )
        data = json.loads(tmpl_result.output)
        # The seeded template has items with ids; we need eval_item id
        # Use the evaluations show or get detail — we'll get it via service
        # For now, add an item then remove it
        tmpl_id = str(data[0]["id"])
        item_result = _invoke(runner, item, ["list", "--json"], seeded_engine)
        item_id = str(json.loads(item_result.output)[0]["id"])

        # Add item
        add_result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "add-item",
                "--item-id",
                item_id,
                "--amount",
                "1",
                "--points",
                "5",
            ],
            seeded_engine,
        )
        assert add_result.exit_code == 0
        # Extract eval_item_id from output
        # Output should mention the id
        m = re.search(r"id=(\d+)\)", add_result.output)
        assert m is not None, f"Could not find ei id in: {add_result.output!r}"
        ei_id = m.group(1)

        # Remove it
        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "remove-item",
                "--eval-item-id",
                ei_id,
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_edit_nonexistent_template(self, runner, seeded_engine):
        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                "9999",
                "rename",
                "--name",
                "X",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_add_item_invalid_item_id(self, runner, seeded_engine):
        tmpl_result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        tmpl_id = str(json.loads(tmpl_result.output)[0]["id"])

        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "add-item",
                "--item-id",
                "9999",
                "--amount",
                "1",
                "--points",
                "5",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_remove_nonexistent_eval_item(self, runner, seeded_engine):
        tmpl_result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        tmpl_id = str(json.loads(tmpl_result.output)[0]["id"])

        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                tmpl_id,
                "remove-item",
                "--eval-item-id",
                "9999",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_remove_item_wrong_template(self, runner, seeded_engine):
        """Removing an item that belongs to a different template fails."""
        # Create a second template
        _invoke(
            runner,
            evaluations,
            ["add", "--inst", "UCR", "--name", "Other template"],
            seeded_engine,
        )
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        other_id = str([d for d in data if d["name"] == "Other template"][0]["id"])

        # Get an eval_item_id from the original (UFide) template
        full_result = _invoke(
            runner,
            evaluations,
            ["list", "--json", "--full"],
            seeded_engine,
        )
        full_data = json.loads(full_result.output)
        ufide_tmpl = [d for d in full_data if d["institution"] == "UFide"][0]
        # We need the actual EvaluationItem id — add one to get it
        item_result = _invoke(runner, item, ["list", "--json"], seeded_engine)
        item_id = str(json.loads(item_result.output)[0]["id"])
        ufide_id = str(ufide_tmpl["id"])

        add_result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                ufide_id,
                "add-item",
                "--item-id",
                item_id,
                "--amount",
                "1",
                "--points",
                "5",
            ],
            seeded_engine,
        )
        m = re.search(r"id=(\d+)\)", add_result.output)
        assert m is not None, f"Could not find ei id in: {add_result.output!r}"
        ei_id = m.group(1)

        # Try removing from the wrong template
        result = _invoke(
            runner,
            evaluations,
            ["edit", other_id, "remove-item", "--eval-item-id", ei_id],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_rename_duplicate_fails(self, runner, seeded_engine):
        # Create a second template for the same institution
        _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "UFide",
                "--name",
                "Parcial UFide",
            ],
            seeded_engine,
        )

        # Get the new template's id
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        new_tmpl = [d for d in data if d["name"] == "Parcial UFide"][0]

        # Try to rename it to the existing name
        result = _invoke(
            runner,
            evaluations,
            [
                "edit",
                str(new_tmpl["id"]),
                "rename",
                "--name",
                "Estudio de caso",
            ],
            seeded_engine,
        )
        assert result.exit_code != 0


# ── P3: evaluations show ────────────────────────────────────────────────


class TestEvaluationsShow:
    def test_show_existing_template(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        tmpl_id = str(json.loads(result.output)[0]["id"])

        result = _invoke(runner, evaluations, ["show", tmpl_id], seeded_engine)
        assert result.exit_code == 0
        assert "Estudio de caso" in result.output
        assert "UFide" in result.output

    def test_show_includes_items(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        tmpl_id = str(json.loads(result.output)[0]["id"])

        result = _invoke(runner, evaluations, ["show", tmpl_id], seeded_engine)
        assert result.exit_code == 0
        assert "SU - Info/Recordar" in result.output
        assert "2 × 5 pts" in result.output

    def test_show_json(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        tmpl_id = str(json.loads(result.output)[0]["id"])

        result = _invoke(
            runner,
            evaluations,
            ["show", tmpl_id, "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Estudio de caso"
        assert data["total_points"] == 26  # 2×5 + 1×16
        assert "items" in data
        assert len(data["items"]) == 2

    def test_show_nonexistent(self, runner, seeded_engine):
        result = _invoke(runner, evaluations, ["show", "9999"], seeded_engine)
        assert result.exit_code != 0

    def test_show_description(self, runner, seeded_engine):
        """Show includes the description field."""
        _invoke(
            runner,
            evaluations,
            [
                "add",
                "--inst",
                "UCR",
                "--name",
                "Parcial con desc",
                "--description",
                "Evaluación parcial del curso.",
            ],
            seeded_engine,
        )
        result = _invoke(runner, evaluations, ["list", "--json"], seeded_engine)
        data = json.loads(result.output)
        tmpl = [d for d in data if d["name"] == "Parcial con desc"][0]

        result = _invoke(
            runner,
            evaluations,
            ["show", str(tmpl["id"]), "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0
        detail = json.loads(result.output)
        assert detail["description"] == "Evaluación parcial del curso."
