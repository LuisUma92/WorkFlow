"""Tests for `workflow validate config` (ITEP-0008 finding 5).

READ-ONLY drift check between a project's config.yaml, workflow.db, and the
filesystem. All fixtures are synthetic under tmp_path -- never touch the live
~/01-U workspace or the live DB.
"""

from __future__ import annotations

import json

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.project import GeneralProject
from workflow.validation.cli import validate


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


def _write_config(tmp_path, subdir, data):
    project_dir = tmp_path / subdir
    project_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = project_dir / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return cfg_path


def _seed_area_and_topic(engine, *, code="60NP", name="NuclearPhysics"):
    with Session(engine) as session:
        area = DisciplineArea(
            code="60NP",
            name="Nuclear Physics",
            discipline_num=60,
            topic_num=0,
            area_initials="NP",
        )
        session.add(area)
        session.flush()
        mt = MainTopic(name=name, code=code, discipline_area_id=area.id)
        session.add(mt)
        session.commit()
        return mt.id


def run_config(engine, *args):
    runner = CliRunner()
    return runner.invoke(
        validate, ["config", *args], obj={"engine": engine}, catch_exceptions=False
    )


class TestValidateConfig:
    def test_stale_path_finding(self, tmp_path, engine):
        cfg = _write_config(
            tmp_path,
            "proj",
            {
                "type": "general",
                "code": "6001NP",
                "name": "Sample",
                "root": "proj",
                "data": {
                    "abs_project_dir": str(tmp_path / "proj"),
                    "abs_parent_dir": str(tmp_path / "does-not-exist"),
                    "abs_src_dir": str(tmp_path / "src"),
                },
            },
        )
        result = run_config(engine, str(cfg), "--json")
        assert result.exit_code == 1
        findings = json.loads(result.output)
        kinds = {f["kind"] for f in findings}
        assert "stale_path" in kinds

    def test_legacy_code_scheme_finding(self, tmp_path, engine):
        cfg = _write_config(
            tmp_path,
            "proj",
            {
                "type": "general",
                "code": "60NP",
                "name": "Sample",
                "root": "proj",
                "data": {
                    "abs_project_dir": str(tmp_path / "proj"),
                    "abs_parent_dir": str(tmp_path),
                    "abs_src_dir": str(tmp_path),
                },
            },
        )
        result = run_config(engine, str(cfg), "--json")
        assert result.exit_code == 1
        findings = json.loads(result.output)
        kinds = {f["kind"] for f in findings}
        assert "legacy_code_scheme" in kinds

    def test_unregistered_finding(self, tmp_path, engine):
        cfg = _write_config(
            tmp_path,
            "proj",
            {
                "type": "general",
                "code": "6001NP",
                "name": "Sample",
                "root": "proj",
                "data": {
                    "abs_project_dir": str(tmp_path / "proj"),
                    "abs_parent_dir": str(tmp_path),
                    "abs_src_dir": str(tmp_path),
                },
            },
        )
        result = run_config(engine, str(cfg), "--json")
        assert result.exit_code == 1
        findings = json.loads(result.output)
        kinds = {f["kind"] for f in findings}
        assert "unregistered" in kinds

    def test_db_mismatch_finding(self, tmp_path, engine):
        mt_id = _seed_area_and_topic(engine, code="6001NP", name="Sample")
        with Session(engine) as session:
            session.add(
                GeneralProject(
                    main_topic_id=mt_id,
                    abs_parent_dir=str(tmp_path / "somewhere-else"),
                    abs_src_dir=str(tmp_path),
                    title="Sample",
                )
            )
            session.commit()

        cfg = _write_config(
            tmp_path,
            "proj",
            {
                "type": "general",
                "code": "6001NP",
                "name": "Sample",
                "root": "proj",
                "data": {
                    "abs_project_dir": str(tmp_path / "proj"),
                    "abs_parent_dir": str(tmp_path),
                    "abs_src_dir": str(tmp_path),
                },
            },
        )
        result = run_config(engine, str(cfg), "--json")
        assert result.exit_code == 1
        findings = json.loads(result.output)
        kinds = {f["kind"] for f in findings}
        assert "db_mismatch" in kinds

    def test_malformed_yaml(self, tmp_path, engine):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        cfg_path = project_dir / "config.yaml"
        cfg_path.write_text("type: [unterminated\n  - broken", encoding="utf-8")

        result = run_config(engine, str(cfg_path), "--json")
        assert result.exit_code == 1
        findings = json.loads(result.output)
        kinds = {f["kind"] for f in findings}
        assert "malformed" in kinds
        # No raw traceback leaked to the user.
        assert "Traceback" not in result.output

    def test_all_consistent_zero_findings(self, tmp_path, engine):
        mt_id = _seed_area_and_topic(engine, code="6001NP", name="Sample")
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        with Session(engine) as session:
            session.add(
                GeneralProject(
                    main_topic_id=mt_id,
                    abs_parent_dir=str(tmp_path),
                    abs_src_dir=str(tmp_path),
                    title="Sample",
                )
            )
            session.commit()

        cfg_path = project_dir / "config.yaml"
        cfg_path.write_text(
            yaml.safe_dump(
                {
                    "type": "general",
                    "code": "6001NP",
                    "name": "Sample",
                    "root": "proj",
                    "data": {
                        "abs_project_dir": str(project_dir),
                        "abs_parent_dir": str(tmp_path),
                        "abs_src_dir": str(tmp_path),
                    },
                }
            ),
            encoding="utf-8",
        )

        result = run_config(engine, str(cfg_path), "--json")
        assert result.exit_code == 0
        findings = json.loads(result.output)
        assert findings == []

    def test_json_output_parseable_with_findings(self, tmp_path, engine):
        cfg = _write_config(
            tmp_path,
            "proj",
            {
                "type": "general",
                "code": "60NP",
                "name": "Sample",
                "root": "proj",
                "data": {
                    "abs_project_dir": str(tmp_path / "proj"),
                    "abs_parent_dir": str(tmp_path / "missing"),
                    "abs_src_dir": str(tmp_path),
                },
            },
        )
        result = run_config(engine, str(cfg), "--json")
        findings = json.loads(result.output)
        assert isinstance(findings, list)
        assert all(
            {"path", "kind", "severity", "detail"} <= set(f.keys()) for f in findings
        )

    def test_real_0060np_case_reproduced(self, tmp_path, engine):
        """Synthetic reproduction of the real ~/01-U/0060NP-NuclearPhysics/config.yaml
        drift (ITEP-0008 finding 5): legacy 2-digit code + stale paths under a
        ~/Documents/01-U tree that does not exist on this machine.
        """
        cfg = _write_config(
            tmp_path,
            "60NP-NuclearPhysics",
            {
                "type": "general",
                "code": "60NP",
                "name": "NuclearPhysics",
                "root": "60NP-NuclearPhysics",
                "data": {
                    "abs_project_dir": str(
                        tmp_path / "Documents" / "01-U" / "00-Fisica" / "60NP-NuclearPhysics"
                    ),
                    "abs_parent_dir": str(tmp_path / "Documents" / "01-U" / "00-Fisica"),
                    "abs_src_dir": str(tmp_path / ".config" / "mytex"),
                },
            },
        )
        result = run_config(engine, str(cfg), "--json")
        assert result.exit_code == 1
        findings = json.loads(result.output)
        kinds = {f["kind"] for f in findings}
        assert "legacy_code_scheme" in kinds
        assert "stale_path" in kinds
