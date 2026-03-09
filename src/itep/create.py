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

from itep.database import (
    Course,
    GeneralProject,
    GeneralProjectBook,
    GeneralProjectTopic,
    LectureInstance,
    MainTopic,
    Book,
    Topic,
    Institution as InstitutionModel,
    get_session,
    init_db,
    seed_reference_data,
)
from itep.defaults import DEF_ABS_PARENT_DIR, DEF_ABS_SRC_DIR
from itep.ioconfig import save_config
from itep.utils import ensure_dir
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
    courses = (
        session.query(Course)
        .filter_by(institution_id=institution.id)
        .all()
    )
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
    topics = [
        cc.content.topic
        for cc in course.course_contents
    ]
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


def create_general(session, parent_dir: Path, src_dir: Path):
    """Create a general_project backed by a main_topic."""
    # 1. Select main_topic
    main_topic = _select_from_db(session, MainTopic, "main topic")
    if not main_topic:
        raise click.ClickException("Cannot proceed without a main topic.")

    # Check uniqueness (1:1)
    existing = (
        session.query(GeneralProject)
        .filter_by(main_topic_id=main_topic.id)
        .first()
    )
    if existing:
        raise click.ClickException(
            f"A general project already exists for {main_topic.name} "
            f"(id={existing.id})."
        )

    # 2. Select topics
    topics = _select_multiple_from_db(session, Topic, "topic")

    # 3. Select books
    books = _select_multiple_from_db(session, Book, "book")

    # 4. Create project
    project = GeneralProject(
        main_topic_id=main_topic.id,
        abs_parent_dir=str(parent_dir),
        abs_src_dir=str(src_dir),
    )
    session.add(project)
    session.flush()  # get project.id

    for topic in topics:
        session.add(GeneralProjectTopic(
            general_project_id=project.id,
            topic_id=topic.id,
        ))
    for book in books:
        session.add(GeneralProjectBook(
            general_project_id=project.id,
            book_id=book.id,
        ))
    session.commit()

    # 5. Create directories
    from itep.models import GeneralProject as GPModel
    root_dir = parent_dir / project.root_dir
    _create_dirs_from_tree(root_dir, GPModel.tree, topics)

    # 6. Write config.yaml
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
    "--parent_dir", "-p", type=click.Path(), default=None,
    help="Parent directory for the project."
)
@click.option(
    "--src_dir", "-s", type=click.Path(), default=None,
    help="Source directory for LaTeX templates."
)
@click.option(
    "--clone", "clone_id", type=int, default=None,
    help="Clone an existing lecture instance by ID."
)
def cli(parent_dir, src_dir, clone_id):
    """Create or clone an ITeP project."""
    parent = Path(parent_dir).expanduser() if parent_dir else DEF_ABS_PARENT_DIR
    src = Path(src_dir).expanduser() if src_dir else DEF_ABS_SRC_DIR

    engine = init_db()
    session = get_session(engine)
    seed_reference_data(session)

    if clone_id:
        clone_cycle(session, clone_id, parent, src)
        return

    project_types = ["lecture", "general"]
    choice = select_enum_type("project type", project_types)

    if choice == "lecture":
        create_lecture(session, parent, src)
    else:
        create_general(session, parent, src)


if __name__ == "__main__":
    cli()
