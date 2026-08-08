"""Service layer for ``workflow project list`` / ``workflow project adopt``.

``adopt_project`` is the non-interactive counterpart of
``itep.create.create_general`` for repos that already exist on disk
(ADR ITEP-0008, findings 3-4 of the 2026-08-08 migration report). It never
creates directories, never writes ``config.yaml``, and never mutates the
adopted directory's contents — it only inserts ``MainTopic`` +
``GeneralProject`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import click
from sqlalchemy.orm import Session

from itep.defaults import DEF_ABS_SRC_DIR
from itep.naming import parse_project_dirname
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.project import GeneralProject, LectureInstance

__all__ = [
    "ProjectRow",
    "AdoptResult",
    "list_projects",
    "adopt_project",
    "get_or_create_area_main_topic",
]


@dataclass(frozen=True)
class ProjectRow:
    """A single row in the unified project listing (general + lecture)."""

    id: int
    kind: str  # "general" | "lecture"
    code: str | None
    title: str
    year_init: int | None
    project_initials: str | None
    status: str | None
    abs_parent_dir: str


@dataclass(frozen=True)
class AdoptResult:
    created: bool
    dry_run: bool
    main_topic_code: str
    title: str
    year_init: int
    project_initials: str
    abs_parent_dir: str
    abs_src_dir: str
    project_id: int | None


def list_projects(session: Session) -> list[ProjectRow]:
    """Return every registered GeneralProject + LectureInstance as rows."""
    rows: list[ProjectRow] = []

    for gp in session.query(GeneralProject).order_by(GeneralProject.id).all():
        rows.append(
            ProjectRow(
                id=gp.id,
                kind="general",
                code=gp.main_topic.code if gp.main_topic else None,
                title=gp.title,
                year_init=gp.year_init,
                project_initials=gp.project_initials,
                status=gp.status,
                abs_parent_dir=gp.abs_parent_dir,
            )
        )

    for li in session.query(LectureInstance).order_by(LectureInstance.id).all():
        course = li.course
        rows.append(
            ProjectRow(
                id=li.id,
                kind="lecture",
                code=course.code if course else None,
                title=course.name if course else "",
                year_init=li.year,
                project_initials=None,
                status=None,
                abs_parent_dir=li.abs_parent_dir,
            )
        )

    return rows


def _resolve_discipline_area(session: Session, area_code: str) -> DisciplineArea:
    area = session.query(DisciplineArea).filter_by(code=area_code).first()
    if area is None:
        raise click.ClickException(
            f"Unknown DisciplineArea code: {area_code}. "
            "Run `workflow db import-codes --all` or verify the directory name."
        )
    return area


def get_or_create_area_main_topic(session: Session, area: DisciplineArea) -> MainTopic:
    existing = session.query(MainTopic).filter_by(code=area.code).first()
    if existing is not None:
        return existing
    mt = MainTopic(
        code=area.code,
        name=area.name,
        parent_id=None,
        discipline_area_id=area.id,
    )
    session.add(mt)
    session.flush()
    return mt


def adopt_project(
    session: Session,
    path: Path,
    *,
    dry_run: bool = False,
) -> AdoptResult:
    """Register an existing repo as a ``GeneralProject``.

    Never creates directories, never writes files, never overwrites disk
    content — only inserts DB rows (unless ``dry_run``).
    """
    if not path.exists():
        raise click.exceptions.Exit(2)
    if not path.is_dir():
        raise click.exceptions.Exit(2)

    parsed = parse_project_dirname(path.name)
    if parsed is None:
        raise click.ClickException(
            f"Directory name {path.name!r} does not match the ADR ITEP-0008 "
            "DDTTAA-YYPP-title format. Refusing to guess."
        )

    area = _resolve_discipline_area(session, parsed.area_code)
    child_code = f"{parsed.area_code}{parsed.year_init:02d}{parsed.project_initials}"

    abs_parent_dir = str(path.parent)
    abs_src_dir = str(DEF_ABS_SRC_DIR)

    existing_mt = session.query(MainTopic).filter_by(code=child_code).first()
    existing_gp = None
    if existing_mt is not None:
        existing_gp = (
            session.query(GeneralProject).filter_by(main_topic_id=existing_mt.id).first()
        )

    if existing_gp is not None:
        return AdoptResult(
            created=False,
            dry_run=dry_run,
            main_topic_code=child_code,
            title=parsed.title,
            year_init=parsed.year_init,
            project_initials=parsed.project_initials,
            abs_parent_dir=abs_parent_dir,
            abs_src_dir=abs_src_dir,
            project_id=existing_gp.id,
        )

    if dry_run:
        return AdoptResult(
            created=False,
            dry_run=True,
            main_topic_code=child_code,
            title=parsed.title,
            year_init=parsed.year_init,
            project_initials=parsed.project_initials,
            abs_parent_dir=abs_parent_dir,
            abs_src_dir=abs_src_dir,
            project_id=None,
        )

    area_topic = get_or_create_area_main_topic(session, area)
    child_topic = MainTopic(
        code=child_code,
        name=parsed.title,
        parent_id=area_topic.id,
        discipline_area_id=area_topic.discipline_area_id,
    )
    session.add(child_topic)
    session.flush()

    gp = GeneralProject(
        main_topic_id=child_topic.id,
        abs_parent_dir=abs_parent_dir,
        abs_src_dir=abs_src_dir,
        year_init=parsed.year_init,
        project_initials=parsed.project_initials,
        title=parsed.title,
        status="active",
    )
    session.add(gp)
    session.commit()

    return AdoptResult(
        created=True,
        dry_run=False,
        main_topic_code=child_code,
        title=parsed.title,
        year_init=parsed.year_init,
        project_initials=parsed.project_initials,
        abs_parent_dir=abs_parent_dir,
        abs_src_dir=abs_src_dir,
        project_id=gp.id,
    )
