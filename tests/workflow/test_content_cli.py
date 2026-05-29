"""workflow content CLI tests — add, list, show."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import DisciplineArea, Topic


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg_content_cli")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _seed_topic(da_code: str = "FI0001", serial: int = 1) -> int:
    engine = init_global_db()
    with Session(engine) as session:
        da = session.scalars(
            __import__("sqlalchemy", fromlist=["select"]).select(DisciplineArea)
            .where(DisciplineArea.code == da_code)
        ).first()
        if da is None:
            da = DisciplineArea(
                code=da_code, name=f"Area {da_code}",
                discipline_num=1, topic_num=serial, area_initials=da_code[:2],
            )
            session.add(da)
            session.flush()
        tp = Topic(discipline_area_id=da.id, name=f"Topic {serial}", serial_number=serial)
        session.add(tp)
        session.commit()
        return tp.id


# ── add ───────────────────────────────────────────────────────────────────


def test_content_add_success_json(runner):
    """add emits JSON with id, topic_id, name; exits 0."""
    topic_id = _seed_topic()
    from workflow.content.cli import content

    result = runner.invoke(content, [
        "add", "--topic-id", str(topic_id), "--name", "MRU", "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["topic_id"] == topic_id
    assert data["name"] == "MRU"
    assert "id" in data


def test_content_add_unknown_topic_id_exits_1(runner):
    """add with unknown topic_id exits 1."""
    from workflow.content.cli import content

    result = runner.invoke(content, [
        "add", "--topic-id", "99999", "--name", "X",
    ])
    assert result.exit_code == 1


def test_content_add_duplicate_name_exits_2(runner):
    """add with duplicate name within the same topic exits 2."""
    topic_id = _seed_topic()
    from workflow.content.cli import content

    runner.invoke(content, ["add", "--topic-id", str(topic_id), "--name", "MRU"])
    result = runner.invoke(content, ["add", "--topic-id", str(topic_id), "--name", "MRU"])
    assert result.exit_code == 2


# ── list ──────────────────────────────────────────────────────────────────


def test_content_list_json_shape(runner):
    """list --json returns array; each element has id, topic_id, name."""
    topic_id = _seed_topic()
    from workflow.content.cli import content

    runner.invoke(content, ["add", "--topic-id", str(topic_id), "--name", "MRU"])
    result = runner.invoke(content, ["list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert {"id", "topic_id", "name"} <= data[0].keys()


def test_content_list_filter_by_topic_id(runner):
    """list --topic-id returns only rows for that topic."""
    t1 = _seed_topic("FI0001", serial=1)
    t2 = _seed_topic("FI0001", serial=2)
    from workflow.content.cli import content

    runner.invoke(content, ["add", "--topic-id", str(t1), "--name", "C1"])
    runner.invoke(content, ["add", "--topic-id", str(t2), "--name", "C2"])
    result = runner.invoke(content, ["list", "--topic-id", str(t1), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["topic_id"] == t1


# ── show ──────────────────────────────────────────────────────────────────


def test_content_show_json(runner):
    """show <id> --json emits correct shape."""
    topic_id = _seed_topic()
    from workflow.content.cli import content

    add_result = runner.invoke(content, [
        "add", "--topic-id", str(topic_id), "--name", "MRU", "--json",
    ])
    content_id = json.loads(add_result.output)["id"]
    result = runner.invoke(content, ["show", str(content_id), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == content_id
    assert data["topic_id"] == topic_id
    assert data["name"] == "MRU"


def test_content_show_not_found_exits_1(runner):
    """show with unknown id exits 1."""
    from workflow.content.cli import content

    result = runner.invoke(content, ["show", "99999"])
    assert result.exit_code == 1


def test_content_list_empty_returns_empty_array(runner):
    """list --json against an empty DB exits 0 and returns an empty JSON array."""
    from workflow.content.cli import content

    result = runner.invoke(content, ["list", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []
