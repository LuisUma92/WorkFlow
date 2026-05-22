"""Unit tests for workflow.vault.paths — resolve_vault_root()."""

from __future__ import annotations

from pathlib import Path

import pytest

from workflow.vault.paths import DEFAULT_VAULT_ROOT, ENV_VAULT_ROOT, resolve_vault_root


def test_resolve_vault_root_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WORKFLOW_VAULT_ROOT env var is used when set."""
    monkeypatch.setenv(ENV_VAULT_ROOT, str(tmp_path))
    assert resolve_vault_root() == tmp_path.resolve()


def test_resolve_vault_root_default_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to DEFAULT_VAULT_ROOT when env var is absent."""
    monkeypatch.delenv(ENV_VAULT_ROOT, raising=False)
    assert resolve_vault_root() == DEFAULT_VAULT_ROOT


def test_resolve_vault_root_empty_string_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty WORKFLOW_VAULT_ROOT is treated the same as unset."""
    monkeypatch.setenv(ENV_VAULT_ROOT, "")
    assert resolve_vault_root() == DEFAULT_VAULT_ROOT


def test_resolve_vault_root_blank_string_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only WORKFLOW_VAULT_ROOT is treated the same as unset."""
    monkeypatch.setenv(ENV_VAULT_ROOT, "   ")
    assert resolve_vault_root() == DEFAULT_VAULT_ROOT


def test_resolve_vault_root_tilde_expansion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WORKFLOW_VAULT_ROOT with ~ is expanded to an absolute path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(ENV_VAULT_ROOT, "~/vault")
    result = resolve_vault_root()
    assert not str(result).startswith("~")
    assert result == (tmp_path / "vault").resolve()
