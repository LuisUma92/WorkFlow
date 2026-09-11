"""Tests for workflow.paths.workspace_root() resolution (ITEP-0008 amendment)."""

from __future__ import annotations

from pathlib import Path


def test_workspace_root_env_var(monkeypatch) -> None:
    """WORKFLOW_WORKSPACE_ROOT env var is highest priority."""
    custom = Path("/tmp/custom_workspace")
    monkeypatch.setenv("WORKFLOW_WORKSPACE_ROOT", str(custom))

    from workflow import paths

    result = paths.workspace_root()
    assert result == custom


def test_workspace_root_default(monkeypatch) -> None:
    """workspace_root defaults to ~/01-U when env var is unset."""
    monkeypatch.delenv("WORKFLOW_WORKSPACE_ROOT", raising=False)

    from workflow import paths

    result = paths.workspace_root()
    assert result == Path.home() / "01-U"


def test_workspace_root_resolved_on_every_call(monkeypatch) -> None:
    """workspace_root() resolves on every call, never cached."""
    from workflow import paths

    monkeypatch.setenv("WORKFLOW_WORKSPACE_ROOT", "/tmp/first")
    first = paths.workspace_root()
    assert first == Path("/tmp/first")

    monkeypatch.setenv("WORKFLOW_WORKSPACE_ROOT", "/tmp/second")
    second = paths.workspace_root()
    assert second == Path("/tmp/second")

    assert first != second


def test_workspace_root_expanduser(monkeypatch) -> None:
    """workspace_root() expands ~ in WORKFLOW_WORKSPACE_ROOT."""
    monkeypatch.setenv("WORKFLOW_WORKSPACE_ROOT", "~/custom")

    from workflow import paths

    result = paths.workspace_root()
    assert "~" not in str(result)
    assert result.is_absolute()


def test_workspace_root_strips_whitespace(monkeypatch) -> None:
    """workspace_root() strips whitespace from env var."""
    monkeypatch.setenv("WORKFLOW_WORKSPACE_ROOT", "  /tmp/padded  ")

    from workflow import paths

    result = paths.workspace_root()
    assert result == Path("/tmp/padded")


def test_workspace_root_empty_string_uses_default(monkeypatch) -> None:
    """workspace_root() uses default when WORKFLOW_WORKSPACE_ROOT is empty string."""
    monkeypatch.setenv("WORKFLOW_WORKSPACE_ROOT", "")

    from workflow import paths

    result = paths.workspace_root()
    assert result == Path.home() / "01-U"
