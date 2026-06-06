"""
workflow.config — config.yaml reader with env > config > default precedence.

Config file location: ``config_dir() / "config.yaml"`` (XDG user config dir).

Known keys (others are passed through without error):
  vault_path          — override for the Zettelkasten vault root path
  default_institution — short name for the default ITeP institution (e.g. "UCR")
  default_timezone    — IANA timezone string (e.g. "America/Costa_Rica")

Missing file → {} (no error).
Malformed YAML or non-dict root → ValueError with a clear message.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

import yaml

from workflow import paths

__all__ = [
    "CONFIG_KEYS",
    "load_config",
    "get_vault_path",
    "get_default_institution",
    "get_default_timezone",
]

CONFIG_KEYS = ("vault_path", "default_institution", "default_timezone")


def load_config() -> dict:
    """Read ``config_dir()/config.yaml`` and return its contents as a dict.

    - Missing file → returns ``{}`` (no error).
    - Present and valid → returns the YAML mapping (all keys passed through).
    - Malformed YAML or non-mapping root → raises ``ValueError``.
    """
    cfg_path = paths.config_dir() / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        raw = cfg_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read config.yaml: {exc}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed config.yaml: {exc}") from exc
    if data is None:
        # Empty file is fine — treat as empty config.
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Malformed config.yaml: expected a YAML mapping at the top level, "
            f"got {type(data).__name__}"
        )
    return data


def get_vault_path(default: Union[str, Path]) -> Path:
    """Return the vault root path with precedence env > config > *default*.

    Precedence:
      1. ``WORKFLOW_VAULT_ROOT`` environment variable (non-empty).
      2. ``vault_path`` key in ``config.yaml``.
      3. *default* argument.
    """
    env_val = (os.environ.get("WORKFLOW_VAULT_ROOT") or "").strip()
    if env_val:
        return Path(env_val).expanduser().resolve()
    cfg = load_config()
    if cfg.get("vault_path"):
        return Path(str(cfg["vault_path"])).expanduser().resolve()
    return Path(default).expanduser().resolve() if not isinstance(default, Path) else default


def get_default_institution(default: str) -> str:
    """Return the default institution short name with precedence config > *default*.

    No environment variable is defined for this key; config.yaml wins over the
    built-in default.
    """
    cfg = load_config()
    val = cfg.get("default_institution")
    if val and isinstance(val, str):
        return val.strip()
    return default


def get_default_timezone(default: str) -> str:
    """Return the default timezone string with precedence config > *default*.

    No environment variable is defined for this key; config.yaml wins over the
    built-in default.
    """
    cfg = load_config()
    val = cfg.get("default_timezone")
    if val and isinstance(val, str):
        return val.strip()
    return default
