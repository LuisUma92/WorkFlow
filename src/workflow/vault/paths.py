"""Vault path resolution — ITEP-0011.

Shared helpers for locating the unified Zettelkasten vault root. Kept in a
dependency-free module so non-CLI consumers (lecture splitter, scanner)
can resolve the vault root without importing the vault CLI.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["DEFAULT_VAULT_ROOT", "ENV_VAULT_ROOT", "resolve_vault_root"]

DEFAULT_VAULT_ROOT = Path.home() / "01-U" / "0000AA-Vault"
ENV_VAULT_ROOT = "WORKFLOW_VAULT_ROOT"


def resolve_vault_root() -> Path:
    """Resolve vault root with precedence: env > config.yaml > ITEP-0011 default.

    Precedence:
      1. ``WORKFLOW_VAULT_ROOT`` env var (existing behaviour, highest priority).
      2. ``vault_path`` key in ``~/.config/workflow/config.yaml`` (lazy import).
      3. ``DEFAULT_VAULT_ROOT`` (``~/01-U/0000AA-Vault``).

    The ``workflow.config`` import is intentionally LAZY (inside this function)
    so that this module stays dependency-free at import time.  Any failure in
    the lazy import or config read silently falls back to ``DEFAULT_VAULT_ROOT``.
    """
    raw = (os.environ.get(ENV_VAULT_ROOT) or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()

    # Lazy import — preserves dependency-free-at-import-time guarantee.
    try:
        from workflow import config as _cfg  # noqa: PLC0415
        cfg = _cfg.load_config()
        vault_path_val = cfg.get("vault_path")
        if vault_path_val:
            return Path(str(vault_path_val)).expanduser().resolve()
    except Exception:  # noqa: BLE001 — any failure → fall back silently
        pass

    return DEFAULT_VAULT_ROOT
