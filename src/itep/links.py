"""
relink — Recreate symlinks from DB data.

Reads config.yaml to get (project_type, project_id), then queries the DB
for topics, books and paths.  Applies symlink rules from models.py templates.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import click

from itep.ioconfig import read_pointer
from itep.structure import GeneralDirectory
from workflow.db.models.project import LectureInstance, GeneralProject
from workflow.db.engine import init_global_db, get_global_session


# ── Symlink helpers ────────────────────────────────────────────────────


def safe_symlink(target: Path, link_path: Path):
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.is_symlink() or link_path.exists():
        if link_path.is_symlink():
            try:
                current = link_path.readlink()
            except OSError:
                current = None
            if current == target:
                return False
            try:
                link_path.unlink()
            except OSError:
                pass
        else:
            return False
    link_path.symlink_to(target)
    return True


def create_config_links(target_dir: Path, abs_src_dir: Path, links_map: dict):
    """Create symlinks for config files (sty, tex templates)."""
    config_dir = target_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for link_name, src_pattern in links_map.items():
        src_file = src_pattern.format(src_dir=str(abs_src_dir))
        safe_symlink(Path(src_file), config_dir / link_name)


# ── Audit ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LinkStatus:
    target: Path
    link_path: Path
    state: str  # OK | MISSING | WRONG_TARGET | BROKEN | NOT_SYMLINK


def audit_symlink(target: Path, link_path: Path) -> LinkStatus:
    if not link_path.exists() and not link_path.is_symlink():
        return LinkStatus(target, link_path, "MISSING")
    if not link_path.is_symlink():
        return LinkStatus(target, link_path, "NOT_SYMLINK")
    try:
        current = link_path.readlink()
    except OSError:
        return LinkStatus(target, link_path, "BROKEN")
    if current != target:
        return LinkStatus(target, link_path, "WRONG_TARGET")
    if not target.exists():
        return LinkStatus(target, link_path, "BROKEN")
    return LinkStatus(target, link_path, "OK")


# ── Expected-link generators (single source of truth) ──────────────────


def iter_lecture_links(instance: LectureInstance) -> Iterator[tuple[Path, Path]]:
    """Yield (target, link_path) for every symlink a lecture project should have."""
    from itep.defaults import get_tex_config

    root = Path(instance.abs_parent_dir) / instance.root_dir
    abs_src = Path(instance.abs_src_dir)
    parent_dir = Path(instance.abs_parent_dir)
    institution = instance.course.institution.short_name
    tex_config = get_tex_config(institution)

    for subdir in ("eval", "lect"):
        for link_name, src_pattern in tex_config.items():
            src_file = src_pattern.format(
                src_dir=str(abs_src),
                institution=institution,
            )
            yield Path(src_file), root / subdir / "config" / link_name

    bib_dir = GeneralDirectory.BIB.value
    img_dir = GeneralDirectory.IMG.value

    topics_seen: dict = {}
    for cc in instance.course.course_contents:
        topic = cc.content.topic
        if topic.id not in topics_seen:
            topics_seen[topic.id] = topic
        for bc in cc.content.bib_links:
            book = bc.bib_entry
            book_dir_name = f"{book.title}_{book.edition}"
            yield (
                parent_dir / img_dir / book_dir_name,
                root / "eval" / "img" / book_dir_name,
            )
            yield (
                parent_dir / img_dir / book_dir_name,
                root / "lect" / "img" / book_dir_name,
            )

    for idx, topic in enumerate(topics_seen.values(), start=1):
        main_t = topic.main_topic.code
        yield (
            parent_dir / bib_dir / main_t,
            root / "lect" / "bib" / main_t,
        )
        yield (
            parent_dir / bib_dir / main_t / topic.name,
            root / "lect" / "bib" / f"{idx:03d}-{topic.name}",
        )


def iter_general_links(project: GeneralProject) -> Iterator[tuple[Path, Path]]:
    """Yield (target, link_path) for every symlink a general project should have."""
    from itep.defaults import get_tex_config

    root = Path(project.abs_parent_dir) / project.root_dir
    abs_src = Path(project.abs_src_dir)
    parent_dir = Path(project.abs_parent_dir)
    tex_config = get_tex_config(None)  # general projects: no institution

    for link_name, src_pattern in tex_config.items():
        src_file = src_pattern.format(src_dir=str(abs_src), institution="")
        yield Path(src_file), root / "config" / link_name

    bib_dir = GeneralDirectory.BIB.value
    img_dir = GeneralDirectory.IMG.value

    for gp_book in project.bib_links:
        book = gp_book.bib_entry
        book_dir_name = f"{book.title}_{book.edition}"
        yield (
            parent_dir / img_dir / book_dir_name,
            root / "img" / book_dir_name,
        )

    for idx, gp_topic in enumerate(project.topic_links, start=1):
        topic = gp_topic.topic
        main_t = topic.main_topic.code
        yield (
            parent_dir / bib_dir / main_t,
            root / "bib" / main_t,
        )
        yield (
            parent_dir / bib_dir / main_t / topic.name,
            root / "bib" / f"{idx:03d}-{topic.name}",
        )


# ── Apply / Audit drivers ──────────────────────────────────────────────


def relink_lecture(instance: LectureInstance):
    root = Path(instance.abs_parent_dir) / instance.root_dir
    for target, link_path in iter_lecture_links(instance):
        safe_symlink(target, link_path)
    click.echo(f"Symlinks recreated for lecture: {root}")


def relink_general(project: GeneralProject):
    root = Path(project.abs_parent_dir) / project.root_dir
    for target, link_path in iter_general_links(project):
        safe_symlink(target, link_path)
    click.echo(f"Symlinks recreated for general project: {root}")


def audit_links(pairs: Iterator[tuple[Path, Path]]) -> list[LinkStatus]:
    return [audit_symlink(t, lp) for t, lp in pairs]


# ── CLI ─────────────────────────────────────────────────────────────────


def _print_audit(statuses: list[LinkStatus]) -> int:
    counts: dict[str, int] = {}
    for s in statuses:
        counts[s.state] = counts.get(s.state, 0) + 1
    width = max((len(s.state) for s in statuses), default=2)
    for s in statuses:
        if s.state == "OK":
            continue
        click.echo(f"{s.state:<{width}}  {s.link_path}  ->  {s.target}")
    summary = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    click.echo(f"\n{summary}  (total={len(statuses)})")
    bad = sum(v for k, v in counts.items() if k != "OK")
    return 1 if bad else 0


@click.command("relink", help="Recreate symlinks from DB for an ITeP project.")
@click.argument("project_dir", required=False)
@click.option("--check", is_flag=True, help="Audit only — report status, no changes.")
@click.option(
    "--list", "list_only", is_flag=True, help="List declared links from DB and exit."
)
def cli(project_dir, check, list_only):
    """Recreate symlinks using config.yaml pointer + DB."""
    target_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    config_file = target_dir / "config.yaml"

    if not config_file.exists():
        raise click.ClickException(f"No config.yaml found in {target_dir}")

    init_global_db()
    pointer = read_pointer(config_file)
    project_type = pointer["project_type"]
    project_id = pointer["project_id"]

    with get_global_session() as session:
        if project_type == "lecture":
            project = session.get(LectureInstance, project_id)
            iter_fn = iter_lecture_links
            relink_fn = relink_lecture
        elif project_type == "general":
            project = session.get(GeneralProject, project_id)
            iter_fn = iter_general_links
            relink_fn = relink_general
        else:
            raise click.ClickException(f"Unknown project_type: {project_type}")

        if project is None:
            raise click.ClickException(
                f"No {project_type} project with id={project_id} in DB."
            )

        if list_only:
            pairs = list(iter_fn(project))
            for target, link_path in pairs:
                click.echo(f"{link_path}  ->  {target}")
            click.echo(f"\ntotal={len(pairs)}")
            return

        if check:
            rc = _print_audit(audit_links(iter_fn(project)))
            raise SystemExit(rc)

        relink_fn(project)


if __name__ == "__main__":
    cli()
