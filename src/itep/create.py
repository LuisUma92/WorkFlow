from itep import structure as stc
from itep.utils import code_format, ensure_dir
from itep.links import create_config_links, create_topics_links

from pathlib import Path
import click


def select_project_type() -> stc.ProjectType:
    selected: stc.ProjectType | None = None
    max_opt = len(stc.ProjectType)
    while not selected:
        print("Choose you project type:")
        for idx, proj in enumerate(stc.ProjectType):
            print(f"\t{idx}: {proj}")
        try:
            choice = int(input("Enter the number for your project type: "))
        except ValueError:
            print("You must write just the option number.\nTry again.")
            continue
        if choice < max_opt:
            selected = list(stc.ProjectType)[choice]
        else:
            print(f"You must choose be between 0 and {max_opt - 1}.\nTry again.")
    return selected


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

    parent_dir
    project_type = select_project_type()

    if project_type == stc.ProjectType.GENE:
        if parent_dir != stc.DEF_ABS_PARENT_DIR:
            print("Your current project directory in not default")
        else:
            print("ok")
    elif project_type == stc.ProjectType.LECT:
        if parent_dir != stc.DEF_ABS_PARENT_DIR / stc.GeneralDirectory.LEC:
            print("Your current project directory in not default")
        else:
            print("ok")
        pass

if __name__ == "__main__":
    cli()
