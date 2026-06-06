"""Tests for `workflow db migrate-xdg` CLI command and itep DB_PATH namespace collapse."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

import workflow.paths as wp
from workflow.db.cli import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_DB_CONTENT = b"SQLite format 3\x00"  # minimal plausible content


def _fake_legacy(tmp_path: Path) -> Path:
    """Create a fake legacy DB file and return its path."""
    legacy_file = tmp_path / "legacy" / "workflow.db"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_bytes(_FAKE_DB_CONTENT)
    return legacy_file


def _xdg_dir(tmp_path: Path) -> Path:
    """Return an XDG data dir rooted at tmp_path (does NOT pre-create workflow.db)."""
    d = tmp_path / "xdg"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# 1. Dry-run (default) — legacy exists, target absent → plan printed, nothing moved
# ---------------------------------------------------------------------------


def test_dry_run_prints_plan_and_changes_nothing(monkeypatch, tmp_path):
    """Default --dry-run: prints migration plan; legacy still exists; target not created."""
    legacy = _fake_legacy(tmp_path)
    xdg = _xdg_dir(tmp_path)
    target = xdg / "workflow.db"

    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy)
    monkeypatch.setattr(wp, "data_dir", lambda: xdg)

    runner = CliRunner()
    result = runner.invoke(db, ["migrate-xdg"])

    assert result.exit_code == 0, result.output
    assert "dry-run" in result.output.lower()
    assert str(legacy) in result.output
    assert str(target) in result.output

    # Nothing actually moved.
    assert legacy.exists(), "Legacy file must still exist after dry-run"
    assert not target.exists(), "Target must NOT be created during dry-run"


# ---------------------------------------------------------------------------
# 2. Real move (--no-dry-run --yes) — legacy moves, backup created
# ---------------------------------------------------------------------------


def test_real_move_creates_target_and_backup(monkeypatch, tmp_path):
    """--no-dry-run --yes: target created, .bak-* backup exists, original gone."""
    legacy = _fake_legacy(tmp_path)
    xdg = _xdg_dir(tmp_path)
    target = xdg / "workflow.db"

    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy)
    monkeypatch.setattr(wp, "data_dir", lambda: xdg)

    runner = CliRunner()
    result = runner.invoke(db, ["migrate-xdg", "--no-dry-run", "--yes"])

    assert result.exit_code == 0, result.output

    # Target must exist and contain the original bytes.
    assert target.exists(), "XDG target must exist after real migration"
    assert target.read_bytes() == _FAKE_DB_CONTENT

    # Legacy original must be gone.
    assert not legacy.exists(), "Legacy file must be gone after real migration"

    # Backup must exist alongside where legacy was.
    backups = list(legacy.parent.glob("workflow.db.bak-*"))
    assert len(backups) == 1, f"Expected exactly one backup, found: {backups}"
    assert backups[0].read_bytes() == _FAKE_DB_CONTENT


# ---------------------------------------------------------------------------
# 3. Idempotent — target already exists → "nothing to do", no change
# ---------------------------------------------------------------------------


def test_idempotent_when_target_exists(monkeypatch, tmp_path):
    """If XDG target already present, command exits 0 with 'nothing to do'."""
    legacy = _fake_legacy(tmp_path)
    xdg = _xdg_dir(tmp_path)
    target = xdg / "workflow.db"
    target.write_bytes(b"existing-db")  # pre-existing target

    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy)
    monkeypatch.setattr(wp, "data_dir", lambda: xdg)

    runner = CliRunner()
    result = runner.invoke(db, ["migrate-xdg", "--no-dry-run", "--yes"])

    assert result.exit_code == 0, result.output
    assert "nothing to do" in result.output.lower()

    # Both files must be unchanged.
    assert target.read_bytes() == b"existing-db"
    assert legacy.exists()


# ---------------------------------------------------------------------------
# 4. Missing legacy — "nothing to do", exit 0
# ---------------------------------------------------------------------------


def test_missing_legacy_exits_cleanly(monkeypatch, tmp_path):
    """If legacy DB is absent, command exits 0 with 'nothing to do'."""
    nonexistent_legacy = tmp_path / "no-such" / "workflow.db"  # never created
    xdg = _xdg_dir(tmp_path)

    monkeypatch.setattr(wp, "legacy_db_path", lambda: nonexistent_legacy)
    monkeypatch.setattr(wp, "data_dir", lambda: xdg)

    runner = CliRunner()
    result = runner.invoke(db, ["migrate-xdg"])

    assert result.exit_code == 0, result.output
    assert "nothing to do" in result.output.lower()


# ---------------------------------------------------------------------------
# 5. itep DB_PATH sits under paths.data_dir() after namespace collapse
# ---------------------------------------------------------------------------


def test_itep_db_path_under_workflow_data_dir():
    """After P3 namespace collapse, itep.defaults.DB_PATH sits under paths.data_dir().

    Asserted as an invariant against the real (unpatched) data_dir — no
    importlib.reload, which would rebind itep.defaults module globals and
    pollute identity-based tests elsewhere (e.g. test_links_audit).
    """
    import itep.defaults as _defaults

    assert _defaults.DB_PATH == wp.data_dir() / "itep.db"
    assert _defaults.DB_PATH.parent == wp.data_dir()
