"""Subsystem defaults derived from WORKFLOW_WORKSPACE_ROOT (ITEP-0008 amendment).

``tests/workflow/test_workspace_root.py`` pins ``workspace_root()`` itself.
This module pins the *derivation contract* around it — the actual point of the
change, per findings 5-7 of
``tasks/requests/2026-08-08-itep-0008-two-layer-directory-contradiction.md``:

  - ``itep.defaults.DEF_ABS_PARENT_DIR`` and the vault root derive from the
    workspace root when their own env var is unset;
  - each stays individually overridable;
  - ``paths.data_dir()`` does NOT derive from it — ADR-0008 pins the global DB
    to the XDG data dir, and deriving it would relocate a live ``workflow.db``.

``itep.defaults`` computes ``DEF_ABS_PARENT_DIR`` at import time (and
``itep.models`` captures it), so the env has to be set *before* the import.
These tests therefore resolve it in a SUBPROCESS rather than with
``importlib.reload``: reloading rebinds module-level dicts such as
``INSTITUTION_TEX_CONFIG`` to fresh objects, which permanently breaks the
identity assertions in ``tests/itep/test_links_audit.py``.  The subprocess form
is also exactly the verification command listed in the request.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from workflow import paths
from workflow.vault import paths as vault_paths

ENV_WORKSPACE = "WORKFLOW_WORKSPACE_ROOT"
ENV_PHYSICS = "WORKFLOW_PHYSICS_DIR"
ENV_VAULT = "WORKFLOW_VAULT_ROOT"

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clean_env(monkeypatch):
    """Clear all three env vars so documented defaults are exercised."""
    for var in (ENV_WORKSPACE, ENV_PHYSICS, ENV_VAULT):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _resolve_physics_dir(**env_overrides: str) -> Path:
    """Import ``itep.defaults`` in a clean subprocess and return DEF_ABS_PARENT_DIR."""
    env = {k: v for k, v in os.environ.items() if k not in (ENV_WORKSPACE, ENV_PHYSICS)}
    env.update(env_overrides)
    env["PYTHONPATH"] = str(_REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", "from itep.defaults import DEF_ABS_PARENT_DIR; print(DEF_ABS_PARENT_DIR)"],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO_ROOT,
        check=True,
    )
    return Path(proc.stdout.strip())


# ── ITeP parent dir derives from the workspace root ────────────────────


def test_physics_dir_derives_from_workspace_root(tmp_path):
    assert _resolve_physics_dir(WORKFLOW_WORKSPACE_ROOT=str(tmp_path)) == tmp_path


def test_physics_dir_env_wins_over_workspace_root(tmp_path):
    resolved = _resolve_physics_dir(
        WORKFLOW_WORKSPACE_ROOT=str(tmp_path / "workspace"),
        WORKFLOW_PHYSICS_DIR=str(tmp_path / "explicit"),
    )
    assert resolved == tmp_path / "explicit"


def test_physics_dir_default_is_not_the_dead_documents_path():
    """Regression: the old default was ~/Documents/01-U/00-Fisica, which does not exist."""
    resolved = _resolve_physics_dir()
    assert resolved == Path.home() / "01-U"
    assert "Documents" not in str(resolved)


# ── Vault root derives from the workspace root ─────────────────────────


def test_vault_root_derives_from_workspace_root(clean_env, tmp_path):
    clean_env.setenv(ENV_WORKSPACE, str(tmp_path))
    assert vault_paths.resolve_vault_root() == tmp_path / "0000AV-Vault"


def test_vault_root_env_wins_over_workspace_root(clean_env, tmp_path):
    clean_env.setenv(ENV_WORKSPACE, str(tmp_path / "workspace"))
    clean_env.setenv(ENV_VAULT, str(tmp_path / "explicit-vault"))
    assert vault_paths.resolve_vault_root() == tmp_path / "explicit-vault"


def test_vault_root_default_unchanged(clean_env):
    assert vault_paths.resolve_vault_root() == Path.home() / "01-U" / "0000AV-Vault"


# ── data_dir() stays XDG (ADR-0008) ────────────────────────────────────


def test_data_dir_is_not_derived_from_workspace_root(clean_env, tmp_path):
    """The global DB must NOT relocate when the workspace root moves."""
    clean_env.setenv(ENV_WORKSPACE, str(tmp_path))
    resolved = paths.data_dir()
    assert resolved != tmp_path
    assert tmp_path not in resolved.parents
