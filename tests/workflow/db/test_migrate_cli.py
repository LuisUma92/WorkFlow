"""Tests for `workflow db migrate` CLI (ITEP-0010)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.cli import db as db_group
from workflow.db.schema_version import current_version


@pytest.fixture
def runner_with_engine(monkeypatch):
    """Patch get_engine_from_ctx to point at an in-memory engine."""
    engine = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(engine)

    monkeypatch.setattr(
        "workflow.db.cli.get_engine_from_ctx", lambda ctx: engine
    )
    return CliRunner(), engine


def test_migrate_runs_baseline(runner_with_engine):
    runner, engine = runner_with_engine
    result = runner.invoke(db_group, ["migrate"])

    assert result.exit_code == 0
    assert "0001_baseline" in result.output
    with Session(engine) as s:
        assert current_version(s, "global") == "0001_baseline"


def test_migrate_idempotent(runner_with_engine):
    runner, engine = runner_with_engine
    runner.invoke(db_group, ["migrate"])
    result2 = runner.invoke(db_group, ["migrate"])

    assert result2.exit_code == 0
    assert "0001_baseline" in result2.output


def test_migrate_dry_run_does_not_stamp(runner_with_engine):
    runner, engine = runner_with_engine
    result = runner.invoke(db_group, ["migrate", "--dry-run"])

    assert result.exit_code == 0
    with Session(engine) as s:
        assert current_version(s, "global") is None


def test_migrate_json_output(runner_with_engine):
    runner, _ = runner_with_engine
    result = runner.invoke(db_group, ["migrate", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "applied" in payload
    assert "skipped" in payload
    assert "head" in payload
    assert "0001_baseline" in payload["applied"]


def test_migrate_status_reports_head(runner_with_engine):
    runner, _ = runner_with_engine
    runner.invoke(db_group, ["migrate"])
    result = runner.invoke(db_group, ["migrate", "status"])

    assert result.exit_code == 0
    assert "0001_baseline" in result.output


def test_migrate_status_json(runner_with_engine):
    runner, _ = runner_with_engine
    runner.invoke(db_group, ["migrate"])
    result = runner.invoke(db_group, ["migrate", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["head"] == "0001_baseline"
    assert "0001_baseline" in payload["applied"]


def test_migrate_status_on_empty_db(runner_with_engine):
    runner, _ = runner_with_engine
    result = runner.invoke(db_group, ["migrate", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["head"] is None
    assert payload["applied"] == []


def test_legacy_itep_0008_subcommand_removed(runner_with_engine):
    runner, _ = runner_with_engine
    result = runner.invoke(db_group, ["migrate", "itep-0008"])

    assert result.exit_code != 0  # should be unknown command


def test_migrate_to_caps_at_revision(runner_with_engine):
    runner, _ = runner_with_engine
    result = runner.invoke(
        db_group, ["migrate", "--to", "0001_baseline", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "0001_baseline" in payload["applied"]
