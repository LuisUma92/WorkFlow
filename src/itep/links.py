from itep.structure import MetaData, ConfigType, Topic, Book
from itep.structure import DEF_ABS_SRC_DIR, DEF_ABS_PARENT_DIR
from itep.utils import load_yaml, create_config_links, create_topics_links
import click
from pathlib import Path

# -------------------- Utilidades --------------------


# -------------------- CLI --------------------


@click.command("relink", help="Recrea symlinks usando config.yaml")
@click.argument("project_dir", required=False)
@click.option(
    "--parent", "abs_parent_dir", default=DEF_ABS_PARENT_DIR, show_default=True
)
@click.option("--src", "abs_src_dir", default=DEF_ABS_SRC_DIR, show_default=True)
def cli(project_dir, abs_parent_dir, abs_src_dir):
    target_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    cfg = load_yaml(target_dir / "config.yaml")
    if not cfg:
        raise click.ClickException("No se pudo leer config.yaml")
    data = MetaData(cfg.get("data"))
    abs_project = Path(data.get("abs_project_dir", abs_parent_dir)).resolve()
    abs_parent = Path(data.get("abs_prarent_dir", abs_parent_dir)).resolve()
    abs_src = Path(data.get("abs_src_dir", abs_src_dir)).resolve()

    topic_list = []
    books_links_relations = {}
    for topic_key, topic_value in cfg["topics"].items():
        for chapter in topic_value["chapters"]:
            if chapter[:3] in cfg["books"]:
                book_info = Book(**cfg["books"][chapter[:3]])
                chapter_src = "{}/{}".format(
                    book_info.get_dir_name(),
                    chapter[3:],
                )
                chapter_link = "{}-{}/{}-{}-{}".format(
                    topic_key[1:],
                    topic_value["name"],
                    book_info.code[:3],
                    book_info.name.lower(),
                    chapter[3:],
                )
                books_links_relations[chapter_link] = chapter_src
        topic_list.append(Topic(topic_value))

    for config_type in ConfigType:
        if config_type.value in cfg.keys():
            relations = cfg[config_type.value]["config_files"]
            create_config_links(abs_project, abs_src, relations, config_type)
        if config_type == ConfigType.EVAL:
            eval_topics_path = abs_project / "eval"
            eval_src_path = abs_parent / "00EE-ExamplesExercises"
            create_topics_links(
                eval_topics_path,
                eval_src_path,
                books_links_relations,
            )

    click.echo("Symlinks recreados según config.yaml.")


if __name__ == "__main__":
    cli()
