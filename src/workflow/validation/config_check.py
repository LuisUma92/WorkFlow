"""
Read-only drift check between a project's config.yaml, workflow.db, and the
filesystem (ITEP-0008 finding 5).

Two config.yaml shapes are recognized:

- **Pointer style** (current, see ``itep.ioconfig``): ``project_type`` +
  ``project_id`` only. Resolved via ``itep.ioconfig.load_config``.
- **Legacy style** (pre-migration, still on disk for older projects, e.g.
  ``~/01-U/0060NP-NuclearPhysics/config.yaml``): ``type``, ``code``, ``name``,
  ``root``, and a ``data`` mapping with ``abs_project_dir``/``abs_parent_dir``/
  ``abs_src_dir``. This is the shape that currently drifts in practice.

This module is READ-ONLY. Nothing here ever writes to config.yaml, the
filesystem, or workflow.db -- it only produces a list of :class:`Finding`
for a human (or a future repair command) to act on.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from itep import ioconfig
from workflow.db.models.knowledge import MainTopic

__all__ = [
    "Finding",
    "check_config",
    "resolve_config_paths",
    "default_config_paths",
]

# ADR ITEP-0008: 4 digits + 2 uppercase letters (e.g. "6001NP").
_DDTTAA_RE = re.compile(r"^\d{4}[A-Z]{2}$")

_LEGACY_REQUIRED_KEYS = ("type", "code", "name", "root", "data")
_LEGACY_PATH_KEYS = ("abs_project_dir", "abs_parent_dir")


@dataclass(frozen=True)
class Finding:
    """A single drift finding for one config.yaml."""

    path: str
    kind: str
    severity: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_config_paths(paths: tuple[str, ...]) -> list[Path]:
    """Expand PATH args (a config.yaml file, or a project dir containing one).

    Does not require the resulting path to exist -- a missing config.yaml is
    reported as a ``malformed`` finding by :func:`check_config`, not raised
    here, so one bad argument never aborts the whole batch.
    """
    resolved: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            resolved.append(p / "config.yaml")
        else:
            resolved.append(p)
    return resolved


def default_config_paths() -> list[Path]:
    """Default PATH set: ``<workspace_root>/*/config.yaml`` (one level deep)."""
    from workflow import paths as wf_paths

    root = wf_paths.workspace_root()
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*/config.yaml") if p.is_file())


def _malformed(path: Path, detail: str) -> list[Finding]:
    return [Finding(str(path), "malformed", "error", detail)]


def _normpath(value: str) -> str:
    return os.path.normpath(os.path.expanduser(value))


def check_config(config_path: Path, session: Session) -> list[Finding]:
    """Check a single config.yaml for drift.  Returns an empty list if clean."""
    if not config_path.exists():
        return _malformed(config_path, "config.yaml not found at this location")

    try:
        raw = ioconfig.read_pointer(config_path)
    except yaml.YAMLError as exc:
        return _malformed(config_path, f"YAML parse error: {exc}")
    except OSError as exc:
        return _malformed(config_path, f"could not read file: {exc}")

    if not isinstance(raw, dict) or not raw:
        return _malformed(config_path, "config.yaml is empty or its root is not a mapping")

    if "project_type" in raw and "project_id" in raw:
        return _check_pointer_style(config_path, raw)
    return _check_legacy_style(config_path, raw, session)


def _check_pointer_style(config_path: Path, raw: dict) -> list[Finding]:
    """Pointer-style config.yaml: resolve via itep.ioconfig.load_config."""
    try:
        ioconfig.load_config(config_path)
    except ValueError as exc:
        return [Finding(str(config_path), "unregistered", "error", str(exc))]
    except KeyError as exc:
        return _malformed(config_path, f"missing required key: {exc}")
    return []


def _check_legacy_style(config_path: Path, raw: dict, session: Session) -> list[Finding]:
    path_str = str(config_path)
    missing = [k for k in _LEGACY_REQUIRED_KEYS if k not in raw]
    if missing:
        return _malformed(
            config_path, f"missing required key(s): {', '.join(missing)}"
        )

    data = raw["data"]
    if not isinstance(data, dict):
        return _malformed(config_path, "'data' key must be a mapping")

    findings: list[Finding] = []
    code = str(raw.get("code") or "")

    if not _DDTTAA_RE.match(code):
        findings.append(
            Finding(
                path_str,
                "legacy_code_scheme",
                "warning",
                f"code '{code}' does not match the DDTTAA scheme "
                "(4 digits + 2 uppercase letters)",
            )
        )

    for key in _LEGACY_PATH_KEYS:
        value = data.get(key)
        if value and not Path(value).expanduser().exists():
            findings.append(
                Finding(
                    path_str,
                    "stale_path",
                    "error",
                    f"data.{key} does not exist on disk: {value}",
                )
            )

    abs_project_dir = data.get("abs_project_dir")
    if abs_project_dir:
        declared = _normpath(str(abs_project_dir))
        actual = _normpath(str(config_path.parent))
        if declared != actual:
            findings.append(
                Finding(
                    path_str,
                    "path_mismatch",
                    "warning",
                    f"config.yaml lives at {actual} but data.abs_project_dir "
                    f"says {declared}",
                )
            )

    findings.extend(_check_db_drift(config_path, raw, data, code, session))
    return findings


def _check_db_drift(
    config_path: Path,
    raw: dict,
    data: dict,
    code: str,
    session: Session,
) -> list[Finding]:
    path_str = str(config_path)
    main_topic = (
        session.query(MainTopic).filter_by(code=code).one_or_none() if code else None
    )
    project = main_topic.general_project if main_topic else None

    if project is None:
        return [
            Finding(
                path_str,
                "unregistered",
                "warning",
                f"no GeneralProject row found in workflow.db for code '{code}'",
            )
        ]

    mismatches: list[str] = []
    config_parent_dir = data.get("abs_parent_dir")
    if config_parent_dir and project.abs_parent_dir:
        if _normpath(str(config_parent_dir)) != _normpath(project.abs_parent_dir):
            mismatches.append(
                "abs_parent_dir: db="
                f"{project.abs_parent_dir!r} config={config_parent_dir!r}"
            )

    config_name = raw.get("name")
    db_title = project.title or main_topic.name
    if config_name and db_title and str(config_name) != db_title:
        mismatches.append(f"name: db={db_title!r} config={config_name!r}")

    if mismatches:
        return [
            Finding(path_str, "db_mismatch", "error", "; ".join(mismatches))
        ]
    return []
