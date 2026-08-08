"""
workflow.paths — single source of truth for XDG path resolution.

Precedence for global_db_path():
  1. WORKFLOW_DATA_DIR env (non-empty)  → $WORKFLOW_DATA_DIR/workflow.db
  2. XDG data dir / workflow.db exists  → platformdirs user_data_dir("workflow")
  3. Legacy path exists                 → ~/01-U/workflow/workflow.db  (+one-time notice)
  4. Default (new install)              → XDG data dir / workflow.db

Symlink-compatible: ``~/.local/share/workflow`` may be a symlink (e.g. pointing to
``<repo>/share/`` in the developer setup).  ``Path.exists()`` follows symlinks, so all
precedence checks and callers work identically whether the data dir is a real directory
or a symlink.

For tests: monkeypatch ``workflow.paths.data_dir`` and/or ``workflow.paths.legacy_db_path``,
or call ``reset_notice_for_tests()`` to reset the one-time legacy notice flag.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import platformdirs

__all__ = [
    "workspace_root",
    "data_dir",
    "config_dir",
    "cache_dir",
    "legacy_db_path",
    "global_db_path",
    "reset_notice_for_tests",
]

_APP = "workflow"

# Academic workspace root (ITEP-0008 amendment 2026-08-08).  Subsystem defaults
# that live *inside* the workspace (ITeP parent dir, Zettelkasten vault) derive
# from this when their own env var is unset.  The XDG data dir does NOT — the
# global DB stays at its XDG location per ADR-0008.
ENV_WORKSPACE_ROOT = "WORKFLOW_WORKSPACE_ROOT"
DEFAULT_WORKSPACE_ROOT = Path.home() / "01-U"

# One-time legacy-fallback notice guard.
_LEGACY_NOTICE_EMITTED: bool = False


def reset_notice_for_tests() -> None:
    """Reset the one-time legacy notice flag.  Call from test teardown or monkeypatch."""
    global _LEGACY_NOTICE_EMITTED
    _LEGACY_NOTICE_EMITTED = False


def workspace_root() -> Path:
    """Return the academic workspace root.

    Precedence:
      1. ``WORKFLOW_WORKSPACE_ROOT`` env var (non-empty).
      2. ``~/01-U`` (ITEP-0008 amendment 2026-08-08).

    Resolved on every call — never cached — so tests and shells that change the
    env var see the new value.  Callers that capture it at import time (e.g.
    ``itep.models``) must be reloaded for a change to take effect.
    """
    raw = (os.environ.get(ENV_WORKSPACE_ROOT) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_WORKSPACE_ROOT


def data_dir() -> Path:
    """Return the XDG user data directory for the workflow app.

    Deliberately NOT derived from :func:`workspace_root` — ADR-0008 pins the
    global DB to the XDG data dir, and deriving it would relocate a live
    database whenever the workspace moves.
    """
    return Path(platformdirs.user_data_dir(_APP))


def config_dir() -> Path:
    """Return the XDG user config directory for the workflow app."""
    return Path(platformdirs.user_config_dir(_APP))


def cache_dir() -> Path:
    """Return the XDG user cache directory for the workflow app."""
    return Path(platformdirs.user_cache_dir(_APP))


def legacy_db_path() -> Path:
    """Return the pre-XDG legacy database path ~/01-U/workflow/workflow.db."""
    return Path("~/01-U/workflow/workflow.db").expanduser()


def _emit_legacy_notice() -> None:
    global _LEGACY_NOTICE_EMITTED
    if not _LEGACY_NOTICE_EMITTED:
        _LEGACY_NOTICE_EMITTED = True
        print(
            "[workflow] Using legacy DB path ~/01-U/workflow/workflow.db. "
            "Run `workflow db migrate-xdg` to migrate to the XDG location.",
            file=sys.stderr,
        )


def global_db_path() -> Path:
    """Resolve the global workflow.db path with XDG-migration precedence.

    Precedence:
      1. WORKFLOW_DATA_DIR env (non-empty)  → $WORKFLOW_DATA_DIR/workflow.db
      2. XDG data dir / workflow.db exists  → platformdirs data dir
      3. Legacy path ~/01-U/workflow/workflow.db exists → legacy (+ one-time notice)
      4. New-install default                → XDG data dir / workflow.db
    """
    env_val = os.environ.get("WORKFLOW_DATA_DIR", "")
    if env_val:
        return Path(env_val).expanduser() / "workflow.db"

    xdg_candidate = data_dir() / "workflow.db"
    if xdg_candidate.exists():
        return xdg_candidate

    legacy = legacy_db_path()
    if legacy.exists():
        _emit_legacy_notice()
        return legacy

    # New install — return XDG path (may not exist yet; callers create it).
    return xdg_candidate
