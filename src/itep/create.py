from itep import structure as strc
from itep.utils import ensure_dir, select_enum_type, gather_input
from itep.utils import set_directory_list, add_to_reference_dict
# from itep.links import create_config_links, create_topics_links

from pathlib import Path
import click

# -------------------- Utilidades --------------------


def gather_code(name: str, patterns: dict) -> str:
    code = ""
    for pattern, condition in patterns.items():
        code += gather_input(
            f"Enter {pattern} for {name}:\n\t<< ",
            condition,
        )
    return code


def gather_name(code: str) -> str:
    name = ""
    while not name:
        name = input(f"Enter the name for {code}:\n\t<< ")
        print(f"You write:\n\t>> {name}")
        ans = input("Is this correct? (Y/n): ").lower() or "y"
        if ans != "y":
            ans = input("Do you want to try again? (Y/n)").lower() or "y"
            if ans == "y":
                name = ""
            else:
                quit()
    return name


# -------------------- CLI --------------------


@click.command("init-tex")
@click.option(
    "--parent_dir",
    "-p",
    type=str,
    required=False,
)
def cli(parent_dir):
    """Create a tex project"""
    parent_dir = Path(parent_dir).expanduser() if parent_dir else Path.cwd()
    ensure_dir(parent_dir, "parent directory")
    project_type = select_enum_type("project type", strc.ProjectType)

    code = gather_code(
        project_type.value["name"],
        project_type.value["patterns"],
    )
    name = gather_name(code)

    meta_data = strc.MetaData(abs_parent_dir=parent_dir)

    admin = None
    if project_type == strc.ProjectType.LECT:
        admin = strc.Admin.gather_info()

    main_topics = set_directory_list(
        parent_dir / project_type.value["main_topics"],
    )

    book_dict = {}
    for topic in main_topics:
        book_dict.update(
            add_to_reference_dict(
                strc.Book,
                parent_dir / project_type.value["main_topics"] / topic,
                "B",
            )
        )
    topics_dict = {}
    for topic in main_topics:
        topics_dict.update(
            add_to_reference_dict(
                strc.Topic,
                parent_dir / project_type.value["main_topics"] / topic,
                "T",
                object_dict={},
            )
        )

    cfg = strc.ProjectStructure(
        code,
        name,
        project_type,
        data=meta_data,
        admin=admin,
        main_topic_root=main_topics,
        books=book_dict,
        topics=topics_dict,
    )
    print(cfg)


if __name__ == "__main__":
    cli()
