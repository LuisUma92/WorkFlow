"""Tests for the `workflow import` verb + `workflow topic import` deprecation
alias + the new `workflow.importer` package location (followup #8).

The engine itself is covered by test_bulk_import_service.py; here we pin only
the new CLI surface and module boundary.
"""
from __future__ import annotations

import json

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import Content, DisciplineArea, Topic


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg_import_verb")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _seed_da(code: str = "FS0001") -> None:
    engine = init_global_db()
    with Session(engine) as session:
        da = DisciplineArea(
            code=code, name=f"Area {code}",
            discipline_num=1, topic_num=1, area_initials=code[:2],
        )
        session.add(da)
        session.commit()


def _valid_yaml_data(da_code: str = "FS0001") -> dict:
    slug = da_code.lower()
    return {
        "discipline_area_code": da_code,
        "topics": [
            {
                "name": "Cinematica",
                "serial": 1,
                "contents": [
                    {
                        "name": "Posicion",
                        "concepts": [
                            {
                                "code": f"{slug}-kin-001",
                                "label": "Vector posicion",
                                "domain": "Información",
                                "description": "",
                                "parent_code": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _write_yaml(tmp_path, data: dict, filename: str = "import.yaml") -> str:
    path = tmp_path / filename
    path.write_text(yaml.dump(data, allow_unicode=True))
    return str(path)


# ── New public module location ────────────────────────────────────────────────


def test_importer_package_exposes_engine_api():
    from workflow.importer import (  # noqa: F401
        ImportSchemaError,
        import_hierarchy,
        load_yaml,
        validate_schema,
    )


def test_old_bulk_import_path_still_reexports():
    """Backward-compat shim: old import path must keep working."""
    from workflow.topic.bulk_import import (  # noqa: F401
        ImportSchemaError,
        import_hierarchy,
        load_yaml,
    )


# ── `workflow import` verb ────────────────────────────────────────────────────


def test_import_verb_inserts_rows(runner, tmp_path):
    _seed_da("FS0001")
    from main import cli

    file = _write_yaml(tmp_path, _valid_yaml_data("FS0001"))
    result = runner.invoke(cli, ["import", file, "--json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["created"]["topics"] == 1
    assert parsed["created"]["contents"] == 1
    assert parsed["created"]["concepts"] == 1

    engine = init_global_db()
    with Session(engine) as session:
        assert session.query(Topic).count() == 1
        assert session.query(Content).count() == 1


def test_import_verb_dry_run_writes_nothing(runner, tmp_path):
    _seed_da("FS0001")
    from main import cli

    file = _write_yaml(tmp_path, _valid_yaml_data("FS0001"))
    result = runner.invoke(cli, ["import", file, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "[DRY-RUN]" in result.output
    engine = init_global_db()
    with Session(engine) as session:
        assert session.query(Topic).count() == 0


def test_import_verb_unknown_da_exits_2(runner, tmp_path):
    from main import cli

    file = _write_yaml(tmp_path, _valid_yaml_data("UNKNOWN"))
    result = runner.invoke(cli, ["import", file])
    assert result.exit_code == 2


# ── `workflow topic import` deprecation alias ─────────────────────────────────


def test_topic_import_alias_still_works(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    file = _write_yaml(tmp_path, _valid_yaml_data("FS0001"))
    result = runner.invoke(topic, ["import", file, "--json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["created"]["topics"] == 1


def test_topic_import_alias_emits_deprecation(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    file = _write_yaml(tmp_path, _valid_yaml_data("FS0001"))
    result = runner.invoke(topic, ["import", file, "--json"])

    assert result.exit_code == 0, result.output
    assert "deprecat" in result.output.lower()
