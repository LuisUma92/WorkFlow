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
    """Resolve vault root from env, fall back to ITEP-0011 default."""
    raw = (os.environ.get(ENV_VAULT_ROOT) or "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_VAULT_ROOT
