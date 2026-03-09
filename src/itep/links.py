"""
relink — Recreate symlinks from DB data.

Reads config.yaml to get (project_type, project_id), then queries the DB
for topics, books and paths.  Applies symlink rules from models.py templates.
"""

from pathlib import Path

import click

from itep.ioconfig import load_config
from itep.structure import GeneralDirectory
from itep.database import (
    LectureInstance,
    GeneralProject,
    init_db,
)


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


# ── Relink from DB ─────────────────────────────────────────────────────


def relink_lecture(instance: LectureInstance):
    """Recreate symlinks for a lecture project."""
    root = Path(instance.abs_parent_dir) / instance.root_dir
    abs_src = Path(instance.abs_src_dir)
    parent_dir = Path(instance.abs_parent_dir)

    # Config links for eval/ and lect/
    from itep.defaults import DEF_TEX_CONFIG
    for subdir in ("eval", "lect"):
        config_dir = root / subdir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        for link_name, src_pattern in DEF_TEX_CONFIG.items():
            src_file = src_pattern.format(
                src_dir=str(abs_src),
                institution=instance.course.institution.short_name,
            )
            safe_symlink(Path(src_file), config_dir / link_name)

    # Book / topic links from course_contents
    bib_dir = GeneralDirectory.BIB.value
    img_dir = GeneralDirectory.IMG.value

    topics_seen = {}
    for cc in instance.course.course_contents:
        topic = cc.content.topic
        if topic.id not in topics_seen:
            topics_seen[topic.id] = topic

        for bc in cc.content.book_links:
            book = bc.book
            book_dir_name = f"{book.name}_{book.edition}"

            # eval/img links
            safe_symlink(
                parent_dir / img_dir / book_dir_name,
                root / "eval" / "img" / book_dir_name,
            )
            # lect/img links
            safe_symlink(
                parent_dir / img_dir / book_dir_name,
                root / "lect" / "img" / book_dir_name,
            )

    # Topic-based bib links
    for idx, topic in enumerate(topics_seen.values(), start=1):
        main_t = topic.main_topic.code
        # lect/bib
        safe_symlink(
            parent_dir / bib_dir / main_t,
            root / "lect" / "bib" / main_t,
        )
        safe_symlink(
            parent_dir / bib_dir / main_t / topic.name,
            root / "lect" / "bib" / f"{idx:03d}-{topic.name}",
        )

    click.echo(f"Symlinks recreated for lecture: {root}")


def relink_general(project: GeneralProject):
    """Recreate symlinks for a general project."""
    root = Path(project.abs_parent_dir) / project.root_dir
    abs_src = Path(project.abs_src_dir)
    parent_dir = Path(project.abs_parent_dir)

    # Config links
    from itep.defaults import DEF_TEX_CONFIG
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for link_name, src_pattern in DEF_TEX_CONFIG.items():
        src_file = src_pattern.format(src_dir=str(abs_src), institution="")
        safe_symlink(Path(src_file), config_dir / link_name)

    bib_dir = GeneralDirectory.BIB.value
    img_dir = GeneralDirectory.IMG.value

    # Book links
    for gp_book in project.book_links:
        book = gp_book.book
        book_dir_name = f"{book.name}_{book.edition}"
        safe_symlink(
            parent_dir / img_dir / book_dir_name,
            root / "img" / book_dir_name,
        )

    # Topic links
    for idx, gp_topic in enumerate(project.topic_links, start=1):
        topic = gp_topic.topic
        main_t = topic.main_topic.code
        safe_symlink(
            parent_dir / bib_dir / main_t,
            root / "bib" / main_t,
        )
        safe_symlink(
            parent_dir / bib_dir / main_t / topic.name,
            root / "bib" / f"{idx:03d}-{topic.name}",
        )

    click.echo(f"Symlinks recreated for general project: {root}")


# ── CLI ─────────────────────────────────────────────────────────────────


@click.command("relink", help="Recreate symlinks from DB for an ITeP project.")
@click.argument("project_dir", required=False)
def cli(project_dir):
    """Recreate symlinks using config.yaml pointer + DB."""
    target_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    config_file = target_dir / "config.yaml"

    if not config_file.exists():
        raise click.ClickException(
            f"No config.yaml found in {target_dir}"
        )

    init_db()
    project = load_config(config_file)

    if isinstance(project, LectureInstance):
        relink_lecture(project)
    elif isinstance(project, GeneralProject):
        relink_general(project)
    else:
        raise click.ClickException(f"Unknown project type: {type(project)}")


if __name__ == "__main__":
    cli()
