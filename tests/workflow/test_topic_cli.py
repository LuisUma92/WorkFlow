"""workflow topic CLI tests — add, list, show."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import DisciplineArea


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg_topic_cli")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _seed_da(code: str = "FI0001") -> int:
    engine = init_global_db()
    with Session(engine) as session:
        da = DisciplineArea(
            code=code, name=f"Area {code}",
            discipline_num=1, topic_num=1, area_initials=code[:2],
        )
        session.add(da)
        session.commit()
        return da.id


# ── add ───────────────────────────────────────────────────────────────────


def test_topic_add_success_json(runner):
    """add emits JSON with id, discipline_area_code, name, serial_number; exits 0."""
    _seed_da("FI0001")
    from workflow.topic.cli import topic

    result = runner.invoke(topic, [
        "add", "--discipline-area", "FI0001",
        "--name", "Cinematica", "--serial", "1", "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["discipline_area_code"] == "FI0001"
    assert data["name"] == "Cinematica"
    assert data["serial_number"] == 1
    assert "id" in data


def test_topic_add_unknown_discipline_area_exits_1(runner):
    """add with unknown DA code exits 1."""
    from workflow.topic.cli import topic

    result = runner.invoke(topic, [
        "add", "--discipline-area", "XXXX00",
        "--name", "X", "--serial", "1",
    ])
    assert result.exit_code == 1


def test_topic_add_duplicate_serial_exits_2(runner):
    """add with duplicate (DA, serial_number) exits 2."""
    _seed_da("FI0001")
    from workflow.topic.cli import topic

    runner.invoke(topic, [
        "add", "--discipline-area", "FI0001", "--name", "Cinematica", "--serial", "1",
    ])
    result = runner.invoke(topic, [
        "add", "--discipline-area", "FI0001", "--name", "Dinamica", "--serial", "1",
    ])
    assert result.exit_code == 2


# ── list ──────────────────────────────────────────────────────────────────


def test_topic_list_json_shape(runner):
    """list --json returns array; each element has required keys."""
    _seed_da("FI0001")
    from workflow.topic.cli import topic

    runner.invoke(topic, [
        "add", "--discipline-area", "FI0001", "--name", "A", "--serial", "1",
    ])
    result = runner.invoke(topic, ["list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert {"id", "name", "serial_number", "discipline_area_code"} <= data[0].keys()


def test_topic_list_filter_by_discipline_area(runner):
    """list --discipline-area returns only rows for that area."""
    _seed_da("FI0001")
    _seed_da("MA0002")
    from workflow.topic.cli import topic

    runner.invoke(topic, ["add", "--discipline-area", "FI0001", "--name", "T1", "--serial", "1"])
    runner.invoke(topic, ["add", "--discipline-area", "MA0002", "--name", "T2", "--serial", "1"])
    result = runner.invoke(topic, ["list", "--discipline-area", "FI0001", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["discipline_area_code"] == "FI0001"


# ── show ──────────────────────────────────────────────────────────────────


def test_topic_show_json(runner):
    """show <id> --json emits correct shape."""
    _seed_da("FI0001")
    from workflow.topic.cli import topic

    add_result = runner.invoke(topic, [
        "add", "--discipline-area", "FI0001",
        "--name", "Cinematica", "--serial", "3", "--json",
    ])
    topic_id = json.loads(add_result.output)["id"]
    result = runner.invoke(topic, ["show", str(topic_id), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == topic_id
    assert data["serial_number"] == 3
    assert data["discipline_area_code"] == "FI0001"


def test_topic_show_not_found_exits_1(runner):
    """show with unknown id exits 1."""
    from workflow.topic.cli import topic

    result = runner.invoke(topic, ["show", "99999"])
    assert result.exit_code == 1
