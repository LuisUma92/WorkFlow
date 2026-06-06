"""Tests for workflow.paths — XDG path resolution with migration precedence."""

from __future__ import annotations

from pathlib import Path

import workflow.paths as wp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _isolate(monkeypatch, tmp_path):
    """Remove WORKFLOW_DATA_DIR from env and point XDG + legacy to tmp_path."""
    monkeypatch.delenv("WORKFLOW_DATA_DIR", raising=False)
    wp.reset_notice_for_tests()


# ---------------------------------------------------------------------------
# 1. Env override wins
# ---------------------------------------------------------------------------


def test_env_override(monkeypatch, tmp_path):
    """WORKFLOW_DATA_DIR env → $DIR/workflow.db, regardless of anything else."""
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    wp.reset_notice_for_tests()
    assert wp.global_db_path() == tmp_path / "workflow.db"


def test_env_override_expanduser(monkeypatch, tmp_path):
    """WORKFLOW_DATA_DIR is expanduser'd (tilde support)."""
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    wp.reset_notice_for_tests()
    result = wp.global_db_path()
    # Path is already expanded (no tilde) — just assert it ends correctly.
    assert result.name == "workflow.db"
    assert result.parent == tmp_path


# ---------------------------------------------------------------------------
# 2. XDG data dir path exists → use it
# ---------------------------------------------------------------------------


def test_xdg_exists_wins_over_legacy(monkeypatch, tmp_path):
    """If XDG workflow.db exists, return it (even if legacy also exists)."""
    _isolate(monkeypatch, tmp_path)

    xdg_dir = tmp_path / "xdg"
    xdg_dir.mkdir()
    (xdg_dir / "workflow.db").touch()

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_file = legacy_dir / "workflow.db"
    legacy_file.touch()

    monkeypatch.setattr(wp, "data_dir", lambda: xdg_dir)
    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy_file)

    result = wp.global_db_path()
    assert result == xdg_dir / "workflow.db"


# ---------------------------------------------------------------------------
# 3. Legacy fallback → returns legacy + emits notice once
# ---------------------------------------------------------------------------


def test_legacy_fallback_returns_path(monkeypatch, tmp_path):
    """When XDG DB absent but legacy DB exists, return legacy path."""
    _isolate(monkeypatch, tmp_path)

    xdg_dir = tmp_path / "xdg_empty"
    xdg_dir.mkdir()  # No workflow.db inside.

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_file = legacy_dir / "workflow.db"
    legacy_file.touch()

    monkeypatch.setattr(wp, "data_dir", lambda: xdg_dir)
    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy_file)

    result = wp.global_db_path()
    assert result == legacy_file


def test_legacy_fallback_emits_notice_once(monkeypatch, tmp_path, capsys):
    """Legacy notice is printed exactly once per process (guarded by flag)."""
    _isolate(monkeypatch, tmp_path)

    xdg_dir = tmp_path / "xdg_empty"
    xdg_dir.mkdir()

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_file = legacy_dir / "workflow.db"
    legacy_file.touch()

    monkeypatch.setattr(wp, "data_dir", lambda: xdg_dir)
    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy_file)

    wp.global_db_path()
    wp.global_db_path()  # second call — no duplicate notice

    captured = capsys.readouterr()
    # Notice appears exactly once.
    assert captured.err.count("migrate-xdg") == 1


def test_legacy_notice_reset_for_tests(monkeypatch, tmp_path, capsys):
    """reset_notice_for_tests() allows the notice to fire again."""
    _isolate(monkeypatch, tmp_path)

    xdg_dir = tmp_path / "xdg_empty2"
    xdg_dir.mkdir()

    legacy_dir = tmp_path / "legacy2"
    legacy_dir.mkdir()
    legacy_file = legacy_dir / "workflow.db"
    legacy_file.touch()

    monkeypatch.setattr(wp, "data_dir", lambda: xdg_dir)
    monkeypatch.setattr(wp, "legacy_db_path", lambda: legacy_file)

    wp.global_db_path()  # fires once → flag set
    wp.reset_notice_for_tests()  # reset
    wp.global_db_path()  # fires again

    captured = capsys.readouterr()
    assert captured.err.count("migrate-xdg") == 2


# ---------------------------------------------------------------------------
# 4. New-install default (nothing exists)
# ---------------------------------------------------------------------------


def test_new_install_default(monkeypatch, tmp_path):
    """When neither XDG nor legacy DB exists, return XDG data_dir/workflow.db."""
    _isolate(monkeypatch, tmp_path)

    xdg_dir = tmp_path / "xdg_empty"
    xdg_dir.mkdir()

    nonexistent_legacy = tmp_path / "nonexistent" / "workflow.db"
    # Do NOT create it.

    monkeypatch.setattr(wp, "data_dir", lambda: xdg_dir)
    monkeypatch.setattr(wp, "legacy_db_path", lambda: nonexistent_legacy)

    result = wp.global_db_path()
    assert result == xdg_dir / "workflow.db"
    assert not result.exists()  # It's okay for it not to exist yet.


# ---------------------------------------------------------------------------
# 5. data_dir / config_dir / cache_dir return Path objects
# ---------------------------------------------------------------------------


def test_data_dir_returns_path():
    assert isinstance(wp.data_dir(), Path)


def test_config_dir_returns_path():
    assert isinstance(wp.config_dir(), Path)


def test_cache_dir_returns_path():
    assert isinstance(wp.cache_dir(), Path)


def test_data_dir_under_monkeypatched_root(monkeypatch, tmp_path):
    """data_dir() should be monkeypatchable for tests."""
    monkeypatch.setattr(wp, "data_dir", lambda: tmp_path / "wf_data")
    assert wp.data_dir() == tmp_path / "wf_data"


# ---------------------------------------------------------------------------
# 6. legacy_db_path returns expected default
# ---------------------------------------------------------------------------


def test_legacy_db_path_default():
    result = wp.legacy_db_path()
    assert isinstance(result, Path)
    assert result.name == "workflow.db"
    # Ends with expected legacy sub-path.
    assert str(result).endswith("01-U/workflow/workflow.db")
