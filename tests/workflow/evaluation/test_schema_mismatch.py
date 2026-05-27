"""Acceptance tests: graceful schema-mismatch handling for the evaluations group.

Covers ITEP-0010 requirement: OperationalError on a missing column/table must
surface as an actionable message (exit 1, "workflow db migrate"), never as a
Python traceback.

Test names match the acceptance criteria in
``tasks/requests/2026-04-29-evaluations-schema-migration.md``.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.cli import db as db_group
from workflow.evaluation.cli import course, evaluations, item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine_with_partial_schema() -> object:
    """SQLite engine with evaluation_template missing the ``description`` column."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE evaluation_template ("
            " id INTEGER PRIMARY KEY,"
            " institution_id INTEGER,"
            " name VARCHAR(80),"
            " template_file VARCHAR(300) DEFAULT ''"
            ")"
        )
    return eng


def _engine_empty() -> object:
    """SQLite engine with no tables at all."""
    return create_engine("sqlite:///:memory:")


def _engine_full() -> object:
    """SQLite engine with up-to-date GlobalBase schema."""
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    return eng


# ---------------------------------------------------------------------------
# test_evaluations_list_schema_mismatch_graceful
# ---------------------------------------------------------------------------


def test_evaluations_list_schema_mismatch_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    """``evaluations list`` exits 1 with actionable message on missing column.

    Acceptance criterion:
        ``workflow evaluations list`` exits 1 with a message containing
        "workflow db migrate", without a Python traceback.
    """
    engine = _engine_with_partial_schema()
    monkeypatch.setattr("workflow.evaluation.cli._get_engine", lambda _ctx: engine)

    runner = CliRunner()
    result = runner.invoke(evaluations, ["list"])

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"
    assert "workflow db migrate" in result.output, (
        f"Actionable hint missing from output:\n{result.output}"
    )
    assert "Traceback" not in result.output, (
        f"Raw traceback leaked into output:\n{result.output}"
    )


def test_evaluations_list_missing_table_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    """``evaluations list`` exits 1 with actionable message on missing table."""
    engine = _engine_empty()
    monkeypatch.setattr("workflow.evaluation.cli._get_engine", lambda _ctx: engine)

    runner = CliRunner()
    result = runner.invoke(evaluations, ["list"])

    assert result.exit_code == 1
    assert "workflow db migrate" in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# test_db_migrate_adds_missing_column
# ---------------------------------------------------------------------------


def test_db_migrate_adds_missing_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """``workflow db migrate`` adds the missing ``description`` column.

    Acceptance criterion:
        Run ``workflow db migrate`` on a DB missing ``description``; column is
        created; subsequent ``evaluations list`` exits 0.
    """
    # Build an engine that already has all other tables (to avoid unrelated errors)
    # but whose evaluation_template lacks description.
    engine = _engine_full()

    # Drop description column by recreating the table without it.
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE evaluation_template RENAME TO _tmp_et")
        conn.exec_driver_sql(
            "CREATE TABLE evaluation_template ("
            " id INTEGER PRIMARY KEY,"
            " institution_id INTEGER,"
            " name VARCHAR(80),"
            " template_file VARCHAR(300) DEFAULT ''"
            ")"
        )
        conn.exec_driver_sql(
            "INSERT INTO evaluation_template (id, institution_id, name)"
            " SELECT id, institution_id, name FROM _tmp_et"
        )
        conn.exec_driver_sql("DROP TABLE _tmp_et")

    monkeypatch.setattr("workflow.db.cli.get_engine_from_ctx", lambda _ctx: engine)

    runner = CliRunner()
    result = runner.invoke(db_group, ["migrate", "--json"])

    assert result.exit_code == 0, f"migrate failed:\n{result.output}"
    payload = json.loads(result.output)
    applied = payload.get("applied", [])
    assert any("0003" in rev for rev in applied), (
        f"Expected 0003 in applied; got: {applied}"
    )

    # After migration, evaluations list must work
    monkeypatch.setattr("workflow.evaluation.cli._get_engine", lambda _ctx: engine)
    result2 = runner.invoke(evaluations, ["list"])
    assert result2.exit_code == 0, (
        f"evaluations list failed after migrate:\n{result2.output}"
    )


# ---------------------------------------------------------------------------
# test_db_migrate_dry_run
# ---------------------------------------------------------------------------


def test_db_migrate_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--dry-run`` prints a plan without modifying the DB.

    Acceptance criterion:
        ``--dry-run`` prints SQL that would run without executing it
        (schema_version table remains empty).
    """
    engine = _engine_full()
    monkeypatch.setattr("workflow.db.cli.get_engine_from_ctx", lambda _ctx: engine)

    from workflow.db.schema_version import current_version

    runner = CliRunner()
    result = runner.invoke(db_group, ["migrate", "--dry-run"])

    assert result.exit_code == 0, f"dry-run exited non-zero:\n{result.output}"
    with Session(engine) as s:
        version = current_version(s, "global")
    # Dry-run must NOT stamp the schema_version table
    assert version is None, (
        f"dry-run must not write schema_version; found: {version}"
    )


# ---------------------------------------------------------------------------
# test_db_migrate_idempotent
# ---------------------------------------------------------------------------


def test_db_migrate_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running ``workflow db migrate`` twice exits 0 with ``applied: []`` on the second run.

    Acceptance criterion:
        ``workflow db migrate`` idempotent — second run reports ``applied: []``.
    """
    engine = _engine_full()
    monkeypatch.setattr("workflow.db.cli.get_engine_from_ctx", lambda _ctx: engine)

    runner = CliRunner()
    runner.invoke(db_group, ["migrate"])
    result2 = runner.invoke(db_group, ["migrate", "--json"])

    assert result2.exit_code == 0, f"Second migrate failed:\n{result2.output}"
    payload = json.loads(result2.output)
    assert payload.get("applied") == [], (
        f"Expected applied=[] on second run; got: {payload.get('applied')}"
    )
