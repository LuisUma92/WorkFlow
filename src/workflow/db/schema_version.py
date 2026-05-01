"""Schema-version tracking for forward-only migrations (ITEP-0010).

A single ``schema_version`` table is created in each base (Global + Local).
Rows are written exclusively by the migration runner; migration ``upgrade``
bodies MUST NOT touch this table.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from workflow.db.base import GlobalBase, LocalBase

__all__ = [
    "GlobalSchemaVersion",
    "LocalSchemaVersion",
    "applied_revisions",
    "current_version",
    "model_for",
    "stamp",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _SchemaVersionMixin:
    revision: Mapped[str] = mapped_column(String(128), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class GlobalSchemaVersion(_SchemaVersionMixin, GlobalBase):
    __tablename__ = "schema_version"


class LocalSchemaVersion(_SchemaVersionMixin, LocalBase):
    __tablename__ = "schema_version"


_MODELS: dict[str, type] = {
    "global": GlobalSchemaVersion,
    "local": LocalSchemaVersion,
}


def model_for(base: str) -> type:
    """Return the SchemaVersion ORM class for the given base."""
    try:
        return _MODELS[base]
    except KeyError as exc:
        raise ValueError(
            f"Unknown base {base!r}; expected 'global' or 'local'."
        ) from exc


def current_version(session: Session, base: str = "global") -> str | None:
    """Return the lexically maximum applied revision, or None if empty."""
    Model = model_for(base)
    rows = session.query(Model.revision).all()
    revisions = sorted(r[0] for r in rows)
    return revisions[-1] if revisions else None


def applied_revisions(session: Session, base: str = "global") -> list[str]:
    """Return all applied revisions in lexical order."""
    Model = model_for(base)
    rows = session.query(Model.revision).all()
    return sorted(r[0] for r in rows)


def stamp(session: Session, revision: str, base: str = "global") -> None:
    """Write a revision row. Caller is responsible for committing."""
    Model = model_for(base)
    session.add(Model(revision=revision))
