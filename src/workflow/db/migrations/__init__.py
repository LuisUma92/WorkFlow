"""Forward-only migration runner for WorkFlow databases (ITEP-0010).

Each migration module under ``migrations/{global,local}/`` exposes:

- ``revision: str`` — lexically sortable identifier (``NNNN_slug``)
- ``description: str`` — short human description
- ``upgrade(connection)`` — applies the migration on an SQLAlchemy Connection

The runner discovers them in lexical order, skips already-applied revisions,
and stamps each successful application in the ``schema_version`` table.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from sqlalchemy import Engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from workflow.db.schema_version import (
    applied_revisions,
    model_for,
    stamp,
)

__all__ = [
    "MigrationStep",
    "RunResult",
    "discover",
    "upgrade",
]


@dataclass(frozen=True)
class MigrationStep:
    """A single migration discovered from a module."""

    revision: str
    description: str
    upgrade: Callable[[Connection], None]
    base: str  # "global" | "local"


@dataclass
class RunResult:
    """Outcome of a runner invocation."""

    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    head: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _default_package_for(base: str) -> str:
    if base not in ("global", "local"):
        raise ValueError(
            f"Unknown base {base!r}; expected 'global' or 'local'."
        )
    return f"workflow.db.migrations.{base}"


def discover(base: str, *, package: str | None = None) -> list[MigrationStep]:
    """Discover migration modules for ``base`` in lexical order.

    ``package`` is overridable for tests; production callers omit it.
    """
    pkg_name = package or _default_package_for(base)
    pkg = importlib.import_module(pkg_name)
    if not getattr(pkg, "__file__", None):
        raise RuntimeError(f"Package {pkg_name!r} has no __file__; cannot scan.")
    pkg_dir = Path(pkg.__file__).parent

    steps: list[MigrationStep] = []
    for path in sorted(pkg_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        modname = f"{pkg_name}.{path.stem}"
        mod = importlib.import_module(modname)
        steps.append(
            MigrationStep(
                revision=mod.revision,
                description=mod.description,
                upgrade=mod.upgrade,
                base=base,
            )
        )
    steps.sort(key=lambda s: s.revision)
    return steps


def upgrade(
    engine: Engine,
    base: str,
    *,
    to: str | None = None,
    dry_run: bool = False,
    steps: list[MigrationStep] | None = None,
) -> RunResult:
    """Apply pending migrations on ``engine`` for ``base``.

    Steps already present in ``schema_version`` are skipped. With ``to``,
    application stops at (and includes) the named revision. With
    ``dry_run=True``, no DDL is executed and no rows are stamped, but the
    returned ``applied`` list reflects what would have run.
    """
    if steps is None:
        steps = discover(base)

    Model = model_for(base)
    Model.__table__.create(engine, checkfirst=True)

    with Session(engine) as s:
        already_applied = set(applied_revisions(s, base))

    result = RunResult()
    for step in steps:
        if step.revision in already_applied:
            result.skipped.append(step.revision)
            continue
        if to is not None and step.revision > to:
            break
        if dry_run:
            result.applied.append(step.revision)
            continue
        with engine.begin() as conn:
            step.upgrade(conn)
        with Session(engine) as s:
            stamp(s, step.revision, base)
            s.commit()
        result.applied.append(step.revision)

    head_set = already_applied | set(result.applied)
    result.head = sorted(head_set)[-1] if head_set else None
    return result
