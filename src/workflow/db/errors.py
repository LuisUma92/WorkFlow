"""Service-layer error bases and schema-guard error translation.

Neutral, domain-agnostic error bases (ADR-0007) are defined here so that
feature modules can inherit from them without creating cross-module import
cycles.  Feature modules' error taxonomies graduate here once a 2nd consumer
appears.

Schema-guard (ITEP-0010): When a Click command opens a session against an
out-of-date DB, SQLAlchemy raises ``OperationalError(no such column: ...)``
or ``no such table: ...``.  The user sees a Python traceback.
``@with_schema_guard`` converts those specific cases into a
``click.ClickException`` whose message points at ``workflow db migrate``.
Any other ``OperationalError`` is re-raised unchanged so genuine bugs surface
normally.

Note: ``SchemaOutOfDateError`` intentionally does NOT inherit ``WorkflowError``;
it is always converted to a ``click.ClickException`` before reaching application
catch-blocks, so it is deliberately outside the service-layer error tree.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from typing import Callable, TypeVar

import click
from sqlalchemy.exc import OperationalError

__all__ = [
    # Neutral service-layer bases
    "WorkflowError",
    "EntityNotFoundError",
    "UniquenessError",
    "AmbiguousLookupError",
    # Schema-guard
    "SchemaOutOfDateError",
    "translate_operational_error",
    "with_schema_guard",
]


# ---------------------------------------------------------------------------
# Neutral, domain-agnostic service-layer error bases (ADR-0007)
# ---------------------------------------------------------------------------


class WorkflowError(Exception):
    """Root of all workflow service-layer errors."""


class EntityNotFoundError(WorkflowError):
    """A requested entity does not exist."""


class UniquenessError(WorkflowError):
    """An operation would violate a uniqueness constraint."""


class AmbiguousLookupError(WorkflowError):
    """A lookup matched 2+ rows where ≤1 was expected."""


_RE_MISSING_COLUMN = re.compile(
    r"no such column:\s+(?:(?P<table>[\w]+)\.)?(?P<name>[\w]+)"
)
_RE_MISSING_TABLE = re.compile(r"no such table:\s+(?P<name>[\w]+)")


@dataclass(frozen=True)
class SchemaOutOfDateError(Exception):
    """Raised when a query hits an absent table or column.

    Carries enough metadata for the user to identify what is missing
    without inspecting the original SQL traceback.
    """

    kind: str  # "column" | "table"
    table: str
    name: str

    def __str__(self) -> str:
        if self.kind == "column":
            target = f"column '{self.name}' on '{self.table}'"
        else:
            target = f"table '{self.table}'"
        return (
            f"Database schema is out of date (missing: {target}). "
            f"Run: workflow db migrate"
        )


def translate_operational_error(exc: OperationalError) -> SchemaOutOfDateError | None:
    """Return a ``SchemaOutOfDateError`` if ``exc`` matches a known schema gap."""
    msg = str(getattr(exc, "orig", exc)) or str(exc)

    m = _RE_MISSING_COLUMN.search(msg)
    if m:
        table = m.group("table") or m.group("name")
        name = m.group("name")
        return SchemaOutOfDateError(kind="column", table=table, name=name)

    m = _RE_MISSING_TABLE.search(msg)
    if m:
        name = m.group("name")
        return SchemaOutOfDateError(kind="table", table=name, name=name)

    return None


F = TypeVar("F", bound=Callable[..., object])


def with_schema_guard(func: F) -> F:
    """Decorator that translates schema-mismatch errors into Click exceptions.

    Wraps a Click command callback. On ``OperationalError`` matching a
    missing column or table, raises ``click.ClickException`` with an
    actionable message and exit code 1. All other exceptions propagate.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OperationalError as exc:
            translated = translate_operational_error(exc)
            if translated is None:
                raise
            raise click.ClickException(str(translated)) from exc

    wrapper._schema_guarded = True  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
