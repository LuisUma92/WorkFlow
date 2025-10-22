"""
CLI to manege tex proyects
"""

from itep import create
from itep.structure import ProjectStructure
from itep.create import create_cfg

import os
import click

from itep.utils import gather_input


cfg = ProjectStructure()

options = {
    "init": {
        "fnc": create_cfg,
        "args": {"parent_dir": None},
    },
}


@click.group("workflow")
def cli():
    pass


@cli.command()
def start():
    its_on = True
    while its_on:
        os.system("clear")
        print(cfg.__dict__)
        opt = input("\t<< ")

        if opt == "exit":
            its_on = False
        elif opt in options.keys():
            for arg in options[opt]["args"]:
                options[opt]["args"][arg] = gather_input(
                    f"Enter {arg} for {opt}\n\t<< ",
                    "^[A-Za-z0-9/.,-_]+",
                )
            options[opt]["fnc"](**options[opt]["args"])


if __name__ == "__main__":
    cli()
