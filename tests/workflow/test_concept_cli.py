"""ITEP-0012.2 — concept CLI tests (CliRunner).

Tests all 6 subcommands: list, show, add, tree, rm, rename.
No monkey-patching of domain types (lessons row 17).
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.knowledge import Concept
from workflow.db.models.notes import NoteConcept, Note
from workflow.concept.cli import concept


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg_concept_cli")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _seed(*, mt_code: str = "FI0006") -> dict:
    """Seed a DisciplineArea + MainTopic and return their DB ids."""
    engine = init_global_db()
    with Session(engine) as session:
        da = DisciplineArea(
            code=mt_code, name="Fisica",
            discipline_num=1, topic_num=6, area_initials="FI",
        )
        session.add(da)
        session.flush()
        mt = MainTopic(code=mt_code, name="Mecanica", discipline_area_id=da.id)
        session.add(mt)
        session.flush()

        c = Concept(code="forces", label="Forces", main_topic_id=mt.id)
        session.add(c)
        session.commit()
        return {"mt_id": mt.id, "concept_id": c.id, "mt_code": mt_code}


def _add_note_concept(concept_id: int, mt_id: int) -> int:
    """Add a Note + NoteConcept row; return note id."""
    engine = init_global_db()
    with Session(engine) as session:
        note = Note(
            zettel_id="cli-note-001",
            filename="cli-note-001.md",
            reference="cli-note-001",
            title="CLI Test Note",
            note_type="permanent",
            main_topic_id=mt_id,
        )
        session.add(note)
        session.flush()
        nc = NoteConcept(note_id=note.id, concept_id=concept_id)
        session.add(nc)
        session.commit()
        return note.id


# ── list ──────────────────────────────────────────────────────────────────


def test_cli_list_empty_returns_empty_json(runner):
    result = runner.invoke(concept, ["list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data == []


def test_cli_list_filtered_by_main_topic(runner):
    _seed(mt_code="FI0006")

    engine = init_global_db()
    with Session(engine) as session:
        da2 = DisciplineArea(
            code="MA0001", name="Calculo",
            discipline_num=2, topic_num=1, area_initials="MA",
        )
        session.add(da2)
        session.flush()
        mt2 = MainTopic(code="MA0001", name="Calculo", discipline_area_id=da2.id)
        session.add(mt2)
        session.flush()
        session.add(Concept(code="integrals", label="Integrals", main_topic_id=mt2.id))
        session.commit()

    result = runner.invoke(concept, ["list", "--main-topic", "FI0006", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    codes = [c["code"] for c in data]
    assert "forces" in codes
    assert "integrals" not in codes


# ── show ──────────────────────────────────────────────────────────────────


def test_cli_show_unknown_exits_nonzero(runner):
    result = runner.invoke(concept, ["show", "no-such-concept"])
    assert result.exit_code != 0
    assert "no-such-concept" in result.output


def test_cli_show_json_shape_locked(runner):
    _seed()
    result = runner.invoke(concept, ["show", "forces", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    expected_keys = {"code", "label", "main_topic", "parent", "description",
                     "id", "child_count", "created_at"}
    assert set(data.keys()) == expected_keys


# ── add ───────────────────────────────────────────────────────────────────


def test_cli_add_happy_path(runner):
    _seed()
    result = runner.invoke(concept, [
        "add", "--code", "newton-2nd",
        "--label", "Newton 2nd Law",
        "--main-topic", "FI0006",
        "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["code"] == "newton-2nd"
    assert data["main_topic"] == "FI0006"
    assert "id" in data


def test_cli_add_duplicate_exits_nonzero(runner):
    _seed()
    result = runner.invoke(concept, [
        "add", "--code", "forces",
        "--label", "Forces Again",
        "--main-topic", "FI0006",
    ])
    assert result.exit_code != 0


def test_cli_add_unknown_main_topic_exits_nonzero(runner):
    result = runner.invoke(concept, [
        "add", "--code", "test-c",
        "--label", "Test",
        "--main-topic", "XX9999",
    ])
    assert result.exit_code != 0


def test_cli_add_unknown_parent_exits_nonzero(runner):
    _seed()
    result = runner.invoke(concept, [
        "add", "--code", "child-c",
        "--label", "Child",
        "--main-topic", "FI0006",
        "--parent", "nonexistent-parent",
    ])
    assert result.exit_code != 0


# ── tree ──────────────────────────────────────────────────────────────────


def test_cli_tree_ascii_renders_hierarchy(runner):
    _seed()
    # Add a child concept
    engine = init_global_db()
    with Session(engine) as session:
        parent = session.query(Concept).filter_by(code="forces").first()
        child = Concept(
            code="gravity", label="Gravity",
            main_topic_id=parent.main_topic_id,
            parent_id=parent.id,
        )
        session.add(child)
        session.commit()

    result = runner.invoke(concept, ["tree", "--main-topic", "FI0006"])
    assert result.exit_code == 0, result.output
    assert "forces" in result.output
    assert "gravity" in result.output


def test_cli_tree_json_nested_shape(runner):
    _seed()
    engine = init_global_db()
    with Session(engine) as session:
        parent = session.query(Concept).filter_by(code="forces").first()
        child = Concept(
            code="gravity", label="Gravity",
            main_topic_id=parent.main_topic_id,
            parent_id=parent.id,
        )
        session.add(child)
        session.commit()

    result = runner.invoke(concept, ["tree", "--main-topic", "FI0006", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0
    root = data[0]
    assert "code" in root
    assert "children" in root
    assert isinstance(root["children"], list)


# ── rm ────────────────────────────────────────────────────────────────────


def test_cli_rm_refuses_without_force_when_referenced(runner):
    seed = _seed()
    _add_note_concept(seed["concept_id"], seed["mt_id"])

    result = runner.invoke(concept, ["rm", "forces"])
    assert result.exit_code != 0
    assert "force" in result.output.lower() or "referenced" in result.output.lower()


def test_cli_rm_force_succeeds(runner):
    seed = _seed()
    _add_note_concept(seed["concept_id"], seed["mt_id"])

    result = runner.invoke(concept, ["rm", "forces", "--force"])
    assert result.exit_code == 0, result.output

    # Verify concept is gone
    result2 = runner.invoke(concept, ["show", "forces"])
    assert result2.exit_code != 0


# ── rename ────────────────────────────────────────────────────────────────


def test_cli_rename_atomic(runner):
    _seed()
    result = runner.invoke(concept, ["rename", "forces", "forces-v2"])
    assert result.exit_code == 0, result.output

    r_old = runner.invoke(concept, ["show", "forces"])
    assert r_old.exit_code != 0

    r_new = runner.invoke(concept, ["show", "forces-v2", "--json"])
    assert r_new.exit_code == 0
    data = json.loads(r_new.output)
    assert data["code"] == "forces-v2"


# ── JSON shape lock ───────────────────────────────────────────────────────


def test_concept_list_json_shape_matches_sibling(runner):
    """Locked key set for concept list --json; additive changes must update this test."""
    _seed()
    result = runner.invoke(concept, ["list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data) > 0
    expected_keys = {"id", "code", "label", "main_topic", "parent", "description"}
    assert set(data[0].keys()) == expected_keys
