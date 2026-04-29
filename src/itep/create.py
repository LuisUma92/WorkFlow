"""
inittex — Create a new ITeP project (lecture or general).

Workflow:
  1. Select project_type (general / lecture)
  2. Select or create entities in DB
  3. Create filesystem directories
  4. Create symlinks
  5. Write minimal config.yaml
"""

from pathlib import Path

import click

from workflow.db.models.academic import (
    Institution as InstitutionModel,
    MainTopic,
    DisciplineArea,
    Course,
)
from workflow.db.models.project import (
    GeneralProject,
    LectureInstance,
)
from workflow.db.engine import get_global_session, init_global_db
from workflow.db.seed import seed_reference_data
from itep.defaults import DEF_ABS_PARENT_DIR, DEF_ABS_SRC_DIR
from itep.ioconfig import save_config
from itep.utils import ensure_dir
from itep import naming
from workflow.db import maturation
from appfunc.iofunc import gather_input
from appfunc.options import select_enum_type

from datetime import date


# ── Helpers ─────────────────────────────────────────────────────────────


def _select_from_db(session, model, label: str, display_attr: str = "name"):
    """Present DB rows as a numbered menu and return the chosen row."""
    rows = session.query(model).all()
    if not rows:
        click.echo(f"No {label} records found in database.")
        return None
    options = [getattr(r, display_attr) for r in rows]
    choice = select_enum_type(label, options)
    idx = options.index(choice)
    return rows[idx]


def _select_multiple_from_db(session, model, label: str, display_attr: str = "name"):
    """Let user pick several rows from a model."""
    selected = []
    rows = session.query(model).all()
    if not rows:
        click.echo(f"No {label} records found in database.")
        return selected
    options = [getattr(r, display_attr) for r in rows]
    enough = False
    while not enough:
        choice = select_enum_type(label, options)
        idx = options.index(choice)
        row = rows[idx]
        if row not in selected:
            selected.append(row)
        names = [getattr(s, display_attr) for s in selected]
        click.echo(f"Selected: {names}")
        ans = input("Add more? (y/N): ").lower() or "n"
        if ans != "y":
            enough = True
    return selected


def _create_dirs_from_tree(
    base_dir: Path,
    tree: list[str],
    topics: list = None,
):
    """Create directory tree, expanding topic placeholders."""
    for directory in tree:
        if "{t_idx" in directory and topics:
            for idx, topic in enumerate(topics, start=1):
                dir_name = directory.format(t_idx=idx, t_name=topic.name)
                ensure_dir(base_dir / dir_name, forced=True)
        else:
            ensure_dir(base_dir / directory, forced=True)


# ── Create: lecture project ────────────────────────────────────────────


def create_lecture(session, parent_dir: Path, src_dir: Path):
    """Create a lecture_instance backed by an existing or new Course."""
    # 1. Select institution
    institution = _select_from_db(
        session, InstitutionModel, "institution", "short_name"
    )
    if not institution:
        raise click.ClickException("Cannot proceed without an institution.")

    # 2. Select or create course
    courses = session.query(Course).filter_by(institution_id=institution.id).all()
    if courses:
        course_options = [f"{c.code} - {c.name}" for c in courses]
        course_options.append("** Create new course **")
        choice = select_enum_type("course", course_options)
        if choice == "** Create new course **":
            course = _create_new_course(session, institution)
        else:
            idx = course_options.index(choice)
            course = courses[idx]
    else:
        click.echo("No courses for this institution. Creating a new one.")
        course = _create_new_course(session, institution)

    # 3. Instance data
    year = int(gather_input("Enter year:", r"2[0-9]{3}"))
    cycle = int(gather_input("Enter cycle (1-3):", r"[1-3]"))
    first_monday_str = gather_input(
        "Enter first monday (YYYY-MM-DD):",
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    )
    first_monday = date.fromisoformat(first_monday_str)

    instance = LectureInstance(
        course_id=course.id,
        year=year,
        cycle=cycle,
        first_monday=first_monday,
        abs_parent_dir=str(parent_dir),
        abs_src_dir=str(src_dir),
    )
    session.add(instance)
    session.commit()

    # 4. Create directories
    from itep.models import LectureProject

    root_dir = parent_dir / instance.root_dir
    topics = [cc.content.topic for cc in course.course_contents]
    _create_dirs_from_tree(root_dir, LectureProject.tree, topics)

    # 5. Write config.yaml
    save_config("lecture", instance.id, root_dir / "config.yaml")
    click.echo(f"Lecture project created: {root_dir}")
    return instance


def _create_new_course(session, institution):
    """Interactively create a new Course record."""
    code = gather_input("Enter course code (e.g. FS0121):", r"[A-Z]{2}[0-9]{4}")
    name = input("Enter course name: ").strip()
    lpw = int(gather_input("Lectures per week:", r"[1-5]"))
    hpl = int(gather_input("Hours per lecture:", r"[1-4]"))

    course = Course(
        institution_id=institution.id,
        code=code,
        name=name,
        lectures_per_week=lpw,
        hours_per_lecture=hpl,
    )
    session.add(course)
    session.commit()
    click.echo(f"Course {code} created.")
    return course


# ── Create: general project ───────────────────────────────────────────


def _select_discipline_area(session) -> DisciplineArea | None:
    """Two-step picker: discipline (DD) → area (DDTTAA)."""
    rows = session.query(DisciplineArea).order_by(DisciplineArea.code).all()
    if not rows:
        click.echo("No discipline areas found. Run `workflow db import-codes --all`.")
        return None
    by_discipline: dict[int, list[DisciplineArea]] = {}
    for r in rows:
        by_discipline.setdefault(r.discipline_num, []).append(r)
    discipline_options = [f"{dd:02d}" for dd in sorted(by_discipline)]
    dd_choice = select_enum_type("discipline (DD)", discipline_options)
    dd = int(dd_choice)
    area_options = [f"{a.code} - {a.name}" for a in by_discipline[dd]]
    area_choice = select_enum_type("area (DDTTAA)", area_options)
    idx = area_options.index(area_choice)
    return by_discipline[dd][idx]


def _get_or_create_area_main_topic(session, area: DisciplineArea) -> MainTopic:
    existing = session.query(MainTopic).filter_by(code=area.code).first()
    if existing is not None:
        return existing
    mt = MainTopic(code=area.code, name=area.name, parent_id=None)
    session.add(mt)
    session.flush()
    return mt


def _prompt_initials(session, area_id: int, yy: int) -> str:
    while True:
        raw = input("Enter project_initials (2 letters A-Z): ").strip()
        try:
            pp = naming.validate_pp(raw)
        except ValueError as e:
            click.echo(str(e))
            continue
        if naming.is_taken(session, area_id, yy, pp):
            click.echo(f"{pp} is already taken in this area for year {yy:02d}.")
            continue
        return pp


def _resolve_discipline_area(session, area_code: str | None) -> DisciplineArea:
    if area_code is not None:
        area_ref = session.query(DisciplineArea).filter_by(code=area_code).first()
        if area_ref is None:
            raise click.ClickException(f"Unknown DisciplineArea code: {area_code}")
        return area_ref
    area_ref = _select_discipline_area(session)
    if not area_ref:
        raise click.ClickException("Cannot proceed without a discipline area.")
    return area_ref


def _confirm_maturation(session, area_topic: MainTopic) -> None:
    signals = maturation.evaluate_area(session, area_topic.id)
    if maturation.is_mature(signals) or not maturation.all_queryable_negative(signals):
        return
    click.echo(
        f"Warning: area {area_topic.code} has no queryable maturation "
        "signals (ADR ITEP-0009 Part II)."
    )
    for s in signals:
        if s.met is False:
            click.echo(f"  ✗ {s.criterion}: {s.evidence}")
    if not click.confirm("Continue anyway?", default=False):
        raise click.Abort()


def _prompt_title() -> str:
    while True:
        value = input("Enter project title: ").strip()
        if value:
            return value
        click.echo("Title cannot be empty.")


def _resolve_project_initials(
    session,
    title: str,
    area_topic: MainTopic,
    yy: int,
    project_initials: str | None,
) -> str:
    if project_initials is not None:
        pp = naming.validate_pp(project_initials)
        if naming.is_taken(session, area_topic.id, yy, pp):
            raise click.ClickException(
                f"{pp} already taken in {area_topic.code} for year {yy:02d}."
            )
        return pp
    cand = naming.derive_project_initials(title, session, area_topic.id, yy)
    if cand is None:
        click.echo(
            "All automatic initials are taken or inapplicable; manual entry required."
        )
        return _prompt_initials(session, area_topic.id, yy)
    click.echo(f"Derived project_initials={cand.value} (rule: {cand.rule}).")
    return cand.value


def create_general(
    session,
    parent_dir: Path,
    src_dir: Path,
    *,
    title: str | None = None,
    year_init: int | None = None,
    project_initials: str | None = None,
    area_code: str | None = None,
    force_no_maturation: bool = False,
):
    """Create a general_project under DDTTAA-YYPP-title (ADR ITEP-0008)."""
    area_ref = _resolve_discipline_area(session, area_code)
    area_topic = _get_or_create_area_main_topic(session, area_ref)
    if not force_no_maturation:
        _confirm_maturation(session, area_topic)

    yy = year_init if year_init is not None else date.today().year % 100
    if title is None:
        title = _prompt_title()
    pp = _resolve_project_initials(session, title, area_topic, yy, project_initials)

    # 6. Create child MainTopic (DDTTAAYYPP).
    child_code = f"{area_topic.code}{yy:02d}{pp}"
    child_topic = MainTopic(
        code=child_code,
        name=title,
        parent_id=area_topic.id,
    )
    session.add(child_topic)
    session.flush()

    # 7. Create GeneralProject row.
    project = GeneralProject(
        main_topic_id=child_topic.id,
        abs_parent_dir=str(parent_dir),
        abs_src_dir=str(src_dir),
        year_init=yy,
        project_initials=pp,
        title=title,
        status="active",
    )
    session.add(project)
    session.commit()

    # 8. Create directory tree.
    from itep.models import GeneralProject as GPModel

    root_dir = parent_dir / project.root_dir
    _create_dirs_from_tree(root_dir, GPModel.tree, [])

    # 9. Write config.yaml.
    save_config("general", project.id, root_dir / "config.yaml")
    click.echo(f"General project created: {root_dir}")
    return project


# ── Clone cycle (lecture only) ─────────────────────────────────────────


def clone_cycle(session, source_id: int, parent_dir: Path = None, src_dir: Path = None):
    """Clone a lecture_instance to a new year/cycle, inheriting the course."""
    source = session.get(LectureInstance, source_id)
    if source is None:
        raise click.ClickException(f"Lecture instance {source_id} not found.")

    year = int(gather_input("Enter year:", r"2[0-9]{3}"))
    cycle = int(gather_input("Enter cycle (1-3):", r"[1-3]"))
    first_monday_str = gather_input(
        "Enter first monday (YYYY-MM-DD):",
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    )

    new_instance = LectureInstance(
        course_id=source.course_id,
        year=year,
        cycle=cycle,
        first_monday=date.fromisoformat(first_monday_str),
        abs_parent_dir=parent_dir or source.abs_parent_dir,
        abs_src_dir=src_dir or source.abs_src_dir,
    )
    session.add(new_instance)
    session.commit()

    from itep.models import LectureProject

    root_dir = Path(new_instance.abs_parent_dir) / new_instance.root_dir
    topics = [cc.content.topic for cc in source.course.course_contents]
    _create_dirs_from_tree(root_dir, LectureProject.tree, topics)

    save_config("lecture", new_instance.id, root_dir / "config.yaml")
    click.echo(f"Cloned lecture project: {root_dir}")
    return new_instance


# ── CLI ─────────────────────────────────────────────────────────────────


@click.command("init-tex")
@click.option(
    "--parent_dir",
    "-p",
    type=click.Path(),
    default=None,
    help="Parent directory for the project.",
)
@click.option(
    "--src_dir",
    "-s",
    type=click.Path(),
    default=None,
    help="Source directory for LaTeX templates.",
)
@click.option(
    "--clone",
    "clone_id",
    type=int,
    default=None,
    help="Clone an existing lecture instance by ID.",
)
@click.option(
    "--force-no-maturation",
    "-f",
    is_flag=True,
    default=False,
    help=(
        "Skip the ADR ITEP-0009 maturation warning when creating a "
        "GeneralProject for an area with no queryable signals."
    ),
)
def cli(parent_dir, src_dir, clone_id, force_no_maturation):
    """Create or clone an ITeP project."""
    parent = Path(parent_dir).expanduser() if parent_dir else DEF_ABS_PARENT_DIR
    src = Path(src_dir).expanduser() if src_dir else DEF_ABS_SRC_DIR

    engine = init_global_db()
    session = get_global_session(engine)
    seed_reference_data(session)

    if clone_id:
        clone_cycle(session, clone_id, parent, src)
        return

    project_types = ["lecture", "general"]
    choice = select_enum_type("project type", project_types)

    if choice == "lecture":
        create_lecture(session, parent, src)
    else:
        create_general(session, parent, src, force_no_maturation=force_no_maturation)


if __name__ == "__main__":
    cli()
