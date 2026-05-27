"""Phase B.3 — `validate notes --strict-main-topic` CLI behavior."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.validation.cli import validate


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _seed_main_topic(code: str = "FI0006") -> int:
    engine = init_global_db()
    with Session(engine) as session:
        da = DisciplineArea(
            code=code, name="Mecánica",
            discipline_num=1, topic_num=6, area_initials="FI",
        )
        session.add(da)
        session.flush()
        mt = MainTopic(code=code, name="Mecánica", discipline_area_id=da.id)
        session.add(mt)
        session.commit()
        return mt.id


def _write_note(path: Path, **fm) -> None:
    body = "---\n"
    body += "id: n-1\ntitle: T\n"
    for k, v in fm.items():
        body += f"{k}: {v!r}\n" if isinstance(v, str) else f"{k}: {v}\n"
    body += "---\n\nbody\n"
    path.write_text(body, encoding="utf-8")


def test_legacy_note_without_main_topic_passes(runner, tmp_path):
    _write_note(tmp_path / "a.md")
    result = runner.invoke(validate, ["notes", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "1 valid" in result.output


def test_unknown_main_topic_warns_by_default(runner, tmp_path):
    _seed_main_topic()
    _write_note(tmp_path / "a.md", main_topic="FI9999")
    result = runner.invoke(validate, ["notes", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "FI9999" in result.output
    assert "1 with warnings" in result.output


def test_unknown_main_topic_strict_errors(runner, tmp_path):
    _seed_main_topic()
    _write_note(tmp_path / "a.md", main_topic="FI9999")
    result = runner.invoke(
        validate, ["notes", str(tmp_path), "--strict-main-topic"]
    )
    assert result.exit_code == 1
    assert "FI9999" in result.output
    assert "1 with errors" in result.output


def test_known_main_topic_passes(runner, tmp_path):
    _seed_main_topic()
    _write_note(tmp_path / "a.md", main_topic="FI0006")
    result = runner.invoke(
        validate, ["notes", str(tmp_path), "--strict-main-topic"]
    )
    assert result.exit_code == 0, result.output
    assert "1 valid" in result.output


def test_discipline_area_mismatch_errors_without_flag(runner, tmp_path):
    """Inconsistency is always an error (Q4 spec) — independent of strict flag."""
    _seed_main_topic("FI0006")
    engine = init_global_db()
    with Session(engine) as session:
        session.add(
            DisciplineArea(
                code="MA0250", name="Cálculo",
                discipline_num=2, topic_num=50, area_initials="MA",
            )
        )
        session.commit()
    _write_note(
        tmp_path / "a.md", main_topic="FI0006", discipline_area="MA0250"
    )
    result = runner.invoke(validate, ["notes", str(tmp_path)])
    assert result.exit_code == 1
    assert "inconsistency" in result.output


def test_consistent_main_topic_and_da_passes(runner, tmp_path):
    _seed_main_topic("FI0006")
    _write_note(
        tmp_path / "a.md", main_topic="FI0006", discipline_area="FI0006"
    )
    result = runner.invoke(
        validate, ["notes", str(tmp_path), "--strict-main-topic"]
    )
    assert result.exit_code == 0, result.output
    assert "1 valid" in result.output
