"""Tests for `workflow topic import` CLI command."""
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
    base = tmp_path_factory.mktemp("xdg_topic_import")
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
                        "name": "Posicion y desplazamiento",
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


# ── Test 1: dry-run → exit 0, summary printed, nothing written ────────────────


def test_dry_run_exits_0_and_writes_nothing(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    data = _valid_yaml_data("FS0001")
    file = _write_yaml(tmp_path, data)

    result = runner.invoke(topic, ["import", file, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "[DRY-RUN]" in result.output

    # Verify nothing was written
    engine = init_global_db()
    with Session(engine) as session:
        assert session.query(Topic).count() == 0
        assert session.query(Content).count() == 0


# ── Test 2: valid file --json → exit 0, rows inserted, JSON shape ─────────────


def test_json_flag_inserts_rows_and_correct_counts(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    data = _valid_yaml_data("FS0001")
    file = _write_yaml(tmp_path, data)

    result = runner.invoke(topic, ["import", file, "--json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["created"]["topics"] == 1
    assert parsed["created"]["contents"] == 1
    assert parsed["created"]["concepts"] == 1
    assert parsed["skipped"] == 0
    assert parsed["errors"] == []

    # Rows actually inserted
    engine = init_global_db()
    with Session(engine) as session:
        assert session.query(Topic).count() == 1
        assert session.query(Content).count() == 1


# ── Test 3: re-run same file → exit 0, all skipped (idempotent) ──────────────


def test_idempotent_rerun_exits_0_all_skipped(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    data = _valid_yaml_data("FS0001")
    file = _write_yaml(tmp_path, data)

    # First run
    runner.invoke(topic, ["import", file, "--json"])
    # Second run
    result = runner.invoke(topic, ["import", file, "--json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["created"]["topics"] == 0
    assert parsed["created"]["contents"] == 0
    assert parsed["skipped"] >= 1


# ── Test 4: unknown discipline_area_code → exit 2, message names the code ────


def test_unknown_discipline_area_exits_2(runner, tmp_path):
    # Do NOT seed any DA
    from workflow.topic.cli import topic

    data = _valid_yaml_data("UNKNOWN")
    file = _write_yaml(tmp_path, data)

    result = runner.invoke(topic, ["import", file])

    assert result.exit_code == 2
    # The error message should name the unknown code
    assert "UNKNOWN" in (result.output + (result.stderr if hasattr(result, "stderr") else ""))


# ── Test 5: malformed YAML → exit 1, no rows written ─────────────────────────


def test_malformed_yaml_exits_1_no_rows(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("key: [unclosed\n  - broken: :")

    result = runner.invoke(topic, ["import", str(bad_file)])

    assert result.exit_code == 1

    engine = init_global_db()
    with Session(engine) as session:
        assert session.query(Topic).count() == 0


# ── Test 6: --json shape has required keys ────────────────────────────────────


def test_json_shape_has_required_keys(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    data = _valid_yaml_data("FS0001")
    file = _write_yaml(tmp_path, data)

    result = runner.invoke(topic, ["import", file, "--json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert "created" in parsed
    assert "skipped" in parsed
    assert "errors" in parsed
    assert isinstance(parsed["errors"], list)
    assert set(parsed["created"].keys()) == {"topics", "contents", "concepts"}


# ── Test 7: partial failure → exit 3, non-empty errors ───────────────────────


def test_partial_failure_exits_3_with_errors(runner, tmp_path):
    _seed_da("FS0001")
    from workflow.topic.cli import topic

    # bad domain value triggers a per-row error inside import_hierarchy
    data = {
        "discipline_area_code": "FS0001",
        "topics": [
            {
                "name": "Topico Bueno",
                "serial": 1,
                "contents": [
                    {
                        "name": "Contenido Bueno",
                        "concepts": [
                            {
                                "code": "fs0001-bad-001",
                                "label": "Concepto malo",
                                "domain": "DOMINIO_INVALIDO_XYZ",
                                "description": "",
                                "parent_code": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    file = _write_yaml(tmp_path, data, "partial.yaml")

    result = runner.invoke(topic, ["import", file, "--json"])

    assert result.exit_code == 3, result.output
    parsed = json.loads(result.stdout)
    assert len(parsed["errors"]) >= 1


# ── Test 8: --discipline-area override works ──────────────────────────────────


def test_discipline_area_override(runner, tmp_path):
    _seed_da("FS0001")
    _seed_da("MA0002")
    from workflow.topic.cli import topic

    # File says FS0001 but we override to MA0002
    data = _valid_yaml_data("FS0001")
    file = _write_yaml(tmp_path, data)

    result = runner.invoke(topic, ["import", file, "--discipline-area", "MA0002", "--json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["created"]["topics"] == 1

    # Topic should belong to MA0002's area
    engine = init_global_db()
    with Session(engine) as session:
        from workflow.db.models.knowledge import DisciplineArea as DA
        ma = session.query(DA).filter_by(code="MA0002").first()
        t = session.query(Topic).filter_by(discipline_area_id=ma.id).first()
        assert t is not None
