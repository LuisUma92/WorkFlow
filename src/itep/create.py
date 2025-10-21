from typing import Dict
from itep import structure as strc
from itep.utils import code_format, ensure_dir, select_enum_type, gather_input
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


def define_new_topics(path: Path, topic: str, idx: int = 1) -> Dict[str, strc.Topic]:
    new_topics = {}
    enough = False
    while not enough:
        msn = f"Do you want to create a new topic on {topic} (y/N): "
        ans = input(msn).lower() or "n"
        if ans == "y":
            ref = code_format("T", idx, max=3)
            new_topics[ref] = strc.Topic.create_directory(path / topic)
            idx += 1
        elif ans == "n":
            enough = True
        else:
            print("Yoy must write 'n' or 'y'.\nTry again")
    return new_topics


def relate_topic_books(
    books: Dict[str, strc.Book],
    topics: Dict[str, strc.Topic],
) -> None:
    for book_id, book in books.items():
        for topic_id, topic in topics.items():
            msn = f"From the book: {book.get_dir_name}\n"
            msn += "Enter chapters numbers asosiated to topic"
            msn += f" {topic_id}-{topic.name}\n"
            msn += "Separate each chapter with 'comma' (,) character.\n"
            msn += "Or enter 'pass' (p) to pass to next topic.\n\t<< "
            ch_str = gather_input(msn, "^[0-9,]+|pass|p")
            if ch_str == "p" or ch_str == "pass":
                continue
            else:
                ch_list = ch_str.split(",")
                for ch in ch_list:
                    topic.add_book_chapter(int(book_id[1:]), int(ch))


def set_week_distribution(
    topics: Dict[str, strc.Topic],
    admin: strc.Admin,
) -> None:
    lectures_to_asigne = []
    idx = 0
    for week in range(1, admin.total_week_count + 1):
        for lecture in range(1, admin.lectures_per_week + 1):
            lecture_code = code_format("W", week)
            lecture_code += code_format("L", lecture)
            lectures_to_asigne.append(lecture_code)
    for _, topic in topics.items():
        lectures_per_topic = int(
            gather_input(
                f"Write the number of lectures for topic {topic.name}\n\t<< ",
                "^[1-9]{1}",
            )
        )
        this_weeks = []
        for lec in lectures_to_asigne[idx : idx + lectures_per_topic]:
            this_weeks.append(lec)

        idx += lectures_per_topic
        topic.weeks = this_weeks


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
                object_dict={},
            )
        )
    topics_dict = {}
    for topic in main_topics:
        topics_dict.update(
            add_to_reference_dict(
                strc.Topic,
                parent_dir / project_type.value["main_topics"] / topic,
                "T",
                max=3,
                object_dict={},
            )
        )
        topics_dict.update(
            define_new_topics(
                parent_dir / project_type.value["main_topics"],
                topic,
                idx=len(topics_dict),
            )
        )

    relate_topic_books(book_dict, topics_dict)

    if project_type == strc.ProjectType.LECT:
        set_week_distribution(topics_dict, admin)

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
    cfg.init_directories()
    cfg.init_links()
    csf.save()


if __name__ == "__main__":
    cli()
