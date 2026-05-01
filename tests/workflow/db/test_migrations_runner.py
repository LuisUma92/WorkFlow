"""Tests for workflow.db.migrations runner (ITEP-0010)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.migrations import (
    MigrationStep,
    RunResult,
    discover,
    upgrade,
)
from workflow.db.schema_version import applied_revisions, current_version


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    return eng


def _step(revision: str, ddl: str | None = None, *, base: str = "global") -> MigrationStep:
    def upgrade_fn(conn):
        if ddl is not None:
            conn.exec_driver_sql(ddl)

    return MigrationStep(
        revision=revision,
        description=f"test step {revision}",
        upgrade=upgrade_fn,
        base=base,
    )


# ── discover ──────────────────────────────────────────────────────────────


def test_discover_returns_lexical_order(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "fake_migrations"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "0002_b.py").write_text(textwrap.dedent("""
        revision = "0002_b"
        description = "second"
        def upgrade(conn): pass
    """))
    (pkg / "0001_a.py").write_text(textwrap.dedent("""
        revision = "0001_a"
        description = "first"
        def upgrade(conn): pass
    """))
    monkeypatch.syspath_prepend(str(tmp_path))

    steps = discover("global", package="fake_migrations")

    assert [s.revision for s in steps] == ["0001_a", "0002_b"]
    assert steps[0].description == "first"
    assert all(s.base == "global" for s in steps)


def test_discover_skips_dunder_files(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "fake2"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "0001_a.py").write_text(textwrap.dedent("""
        revision = "0001_a"
        description = "x"
        def upgrade(conn): pass
    """))
    monkeypatch.syspath_prepend(str(tmp_path))

    steps = discover("global", package="fake2")

    assert [s.revision for s in steps] == ["0001_a"]


def test_discover_module_missing_revision_raises(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "fake3"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "0001_bad.py").write_text("def upgrade(conn): pass\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(AttributeError):
        discover("global", package="fake3")


# ── upgrade ────────────────────────────────────────────────────────────────


def test_upgrade_applies_pending_steps(engine):
    steps = [
        _step("0001_create", "CREATE TABLE t1 (id INT)"),
        _step("0002_more", "CREATE TABLE t2 (id INT)"),
    ]
    result = upgrade(engine, "global", steps=steps)

    assert isinstance(result, RunResult)
    assert result.applied == ["0001_create", "0002_more"]
    assert result.skipped == []
    assert result.head == "0002_more"

    with Session(engine) as s:
        assert applied_revisions(s, "global") == ["0001_create", "0002_more"]
        assert current_version(s, "global") == "0002_more"
    insp = inspect(engine)
    assert "t1" in insp.get_table_names()
    assert "t2" in insp.get_table_names()


def test_upgrade_idempotent_on_second_run(engine):
    steps = [_step("0001_create", "CREATE TABLE t1 (id INT)")]
    upgrade(engine, "global", steps=steps)
    result2 = upgrade(engine, "global", steps=steps)

    assert result2.applied == []
    assert result2.skipped == ["0001_create"]
    assert result2.head == "0001_create"


def test_upgrade_to_caps_at_revision(engine):
    steps = [
        _step("0001_a", "CREATE TABLE a (id INT)"),
        _step("0002_b", "CREATE TABLE b (id INT)"),
        _step("0003_c", "CREATE TABLE c (id INT)"),
    ]
    result = upgrade(engine, "global", to="0002_b", steps=steps)

    assert result.applied == ["0001_a", "0002_b"]
    insp = inspect(engine)
    assert "a" in insp.get_table_names()
    assert "b" in insp.get_table_names()
    assert "c" not in insp.get_table_names()


def test_upgrade_dry_run_does_not_modify_db(engine):
    steps = [_step("0001_a", "CREATE TABLE a (id INT)")]
    result = upgrade(engine, "global", dry_run=True, steps=steps)

    assert result.applied == ["0001_a"]
    insp = inspect(engine)
    assert "a" not in insp.get_table_names()
    with Session(engine) as s:
        assert current_version(s, "global") is None


def test_upgrade_creates_schema_version_table_if_absent():
    engine = create_engine("sqlite:///:memory:")
    # No metadata.create_all — schema_version absent
    steps = [_step("0001_a", "CREATE TABLE a (id INT)")]
    upgrade(engine, "global", steps=steps)
    insp = inspect(engine)
    assert "schema_version" in insp.get_table_names()


def test_upgrade_with_no_steps_returns_empty(engine):
    result = upgrade(engine, "global", steps=[])
    assert result.applied == []
    assert result.skipped == []
    assert result.head is None


def test_upgrade_partial_history_resumes(engine):
    """A DB stamped at an earlier revision applies only newer pending steps."""
    with Session(engine) as s:
        from workflow.db.schema_version import stamp
        stamp(s, "0001_a", "global")
        s.commit()

    steps = [
        _step("0001_a", "CREATE TABLE a (id INT)"),  # already applied
        _step("0002_b", "CREATE TABLE b (id INT)"),
    ]
    result = upgrade(engine, "global", steps=steps)

    assert result.applied == ["0002_b"]
    assert result.skipped == ["0001_a"]
    assert result.head == "0002_b"
    insp = inspect(engine)
    assert "a" not in insp.get_table_names()  # was not re-created
    assert "b" in insp.get_table_names()


def test_upgrade_real_global_package_discovers_and_runs(engine):
    """Smoke test against the real workflow.db.migrations.global package."""
    result = upgrade(engine, "global")

    # 0001_baseline must exist; result must include it
    assert "0001_baseline" in (result.applied + result.skipped)
    assert result.head == "0001_baseline" or result.head > "0001_baseline"

    with Session(engine) as s:
        assert "0001_baseline" in applied_revisions(s, "global")


def test_upgrade_real_local_package_runs():
    eng = create_engine("sqlite:///:memory:")
    from workflow.db.base import LocalBase
    LocalBase.metadata.create_all(eng)

    result = upgrade(eng, "local")

    assert "0001_baseline" in (result.applied + result.skipped)


def test_run_result_to_dict():
    r = RunResult(applied=["0001_a"], skipped=["0000_x"], head="0001_a")
    d = r.to_dict()
    assert d == {"applied": ["0001_a"], "skipped": ["0000_x"], "head": "0001_a"}


# Quiet imports of `text` if unused
_ = text
