"""
ITEP-0008 schema migration.

Adds:
  - ``main_topic.parent_id`` (nullable self-FK).
  - ``general_project.year_init``, ``project_initials``, ``title``, ``status``,
    ``archived_at``.
  - ``discipline_area`` reference table.

Optionally backfills area-level ``MainTopic`` rows and reassigns ``parent_id``
on a caller-supplied mapping. Designed to be idempotent: re-running on an
already-migrated DB is a no-op.

Entry point: ``run_migration(engine, backfill=None) -> MigrationReport``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.academic import MainTopic


# ── Column specs ──────────────────────────────────────────────────────────


# (column_name, sqlite-typed DDL fragment)
_MAIN_TOPIC_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("parent_id", "INTEGER REFERENCES main_topic(id)"),
)

_GENERAL_PROJECT_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("year_init", "INTEGER NOT NULL DEFAULT 0"),
    ("project_initials", "VARCHAR(2) NOT NULL DEFAULT ''"),
    ("title", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("status", "VARCHAR(20) NOT NULL DEFAULT 'active'"),
    ("archived_at", "DATE"),
)


# ── Report ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BackfillRequest:
    """Caller-supplied mapping for area creation + child reassignment.

    ``area_code`` (e.g. ``"0060NP"``) is created as a MainTopic with
    ``parent_id=NULL`` if missing. Each item in ``children`` is a tuple
    ``(child_code, year_init, project_initials, title)``; the matching
    existing MainTopic row (filtered by ``code == child_code``) is updated to
    point at the area, and its 1:1 ``GeneralProject`` (if any) gets the
    supplied ``year_init/project_initials/title`` written if currently blank.
    """

    area_code: str
    area_name: str
    children: tuple[tuple[str, int, str, str], ...] = ()


@dataclass
class MigrationReport:
    columns_added: list[str] = field(default_factory=list)
    tables_created: list[str] = field(default_factory=list)
    areas_created: list[str] = field(default_factory=list)
    children_reassigned: list[str] = field(default_factory=list)
    projects_backfilled: list[str] = field(default_factory=list)
    columns_skipped: list[str] = field(default_factory=list)
    tables_skipped: list[str] = field(default_factory=list)
    children_skipped: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────


def _existing_columns(engine: Engine, table: str) -> set[str]:
    inspector = inspect(engine)
    if not inspector.has_table(table):
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def _existing_tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


_ALLOWED_TABLES: frozenset[str] = frozenset({"main_topic", "general_project"})
_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _add_columns(
    engine: Engine,
    table: str,
    columns: Iterable[tuple[str, str]],
    report: MigrationReport,
) -> None:
    if table not in _ALLOWED_TABLES:
        raise ValueError(
            f"Refusing to ALTER unknown table {table!r}; "
            f"_add_columns is restricted to {_ALLOWED_TABLES}."
        )
    have = _existing_columns(engine, table)
    if not have:
        report.tables_skipped.append(table)
        return
    with engine.begin() as conn:
        for name, ddl in columns:
            if not _IDENTIFIER_RE.match(name):
                raise ValueError(
                    f"Refusing to ALTER column with non-identifier name {name!r}."
                )
            if name in have:
                report.columns_skipped.append(f"{table}.{name}")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            report.columns_added.append(f"{table}.{name}")


def _apply_backfill(
    session: Session, request: BackfillRequest, report: MigrationReport
) -> None:
    area = session.query(MainTopic).filter_by(code=request.area_code).first()
    if area is None:
        area = MainTopic(
            code=request.area_code,
            name=request.area_name,
            parent_id=None,
        )
        session.add(area)
        session.flush()
        report.areas_created.append(request.area_code)

    for child_code, yy, pp, title in request.children:
        child = session.query(MainTopic).filter_by(code=child_code).first()
        if child is None or child.id == area.id:
            report.children_skipped.append(child_code)
            continue
        if child.parent_id != area.id:
            child.parent_id = area.id
            report.children_reassigned.append(child_code)

        gp = child.general_project
        if gp is None:
            continue
        # Use the title sentinel: an empty title means the project has never
        # been backfilled (NOT NULL DEFAULT '' from the legacy ALTER). Once a
        # title is written, subsequent runs leave it alone — making the
        # backfill safely idempotent even if year_init happens to be 0.
        if not gp.title:
            gp.year_init = yy
            gp.project_initials = pp
            gp.title = title
            report.projects_backfilled.append(child_code)


# ── Entry point ───────────────────────────────────────────────────────────


def run_migration(
    engine: Engine,
    backfill: BackfillRequest | None = None,
) -> MigrationReport:
    """Apply ITEP-0008 schema changes idempotently.

    ``GlobalBase.metadata.create_all`` covers fresh databases. For existing
    databases this function emits the missing ``ALTER TABLE`` statements and
    creates the ``discipline_area`` table when absent. Passing a
    ``BackfillRequest`` additionally creates an area-level ``MainTopic`` and
    reassigns ``parent_id`` for the listed child codes.
    """

    report = MigrationReport()

    before = _existing_tables(engine)
    GlobalBase.metadata.create_all(bind=engine)
    after = _existing_tables(engine)
    report.tables_created.extend(sorted(after - before))

    _add_columns(engine, "main_topic", _MAIN_TOPIC_NEW_COLUMNS, report)
    _add_columns(engine, "general_project", _GENERAL_PROJECT_NEW_COLUMNS, report)

    if backfill is not None:
        with Session(engine) as session:
            try:
                _apply_backfill(session, backfill, report)
                session.commit()
            except Exception:
                session.rollback()
                raise

    return report
