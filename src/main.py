"""
CLI to manege tex proyects
"""

from itep.structure import ProjectStructure
from itep.utils import gather_input
from itep.create import create_cfg
from itep import manager

import os
import click
from inspect import getmembers, isfunction


cfg = ProjectStructure()

options = {
    "init": {
        "fnc": create_cfg,
        "args": {"parent_dir": None},
    },
}


def help():
    for foo, _ in getmembers(manager, isfunction):
        print(
            getattr(manager, foo).__name__,
            getattr(manager, foo).__annotations__,
        )


@click.group("workflow")
def cli():
    pass


@cli.command()
def start():
    global cfg
    its_on = True
    while its_on:
        os.system("clear")
        print(dict(cfg))
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
        elif opt == "help":
            # opt_list = [getattr(manager, o) for o in getmanager]
            help()
            input()
        else:
            opt = getattr(manager, opt)
            print(f"Enter values for {opt.__name__} as list")
            print(opt.__annotations__)
            args = eval(
                gather_input(
                    f"Enter args for {opt}\n\t<< ",
                    "^[A-Za-z0-9/.:,'_-{}()[]]+",
                )
            )
            cfg = opt(cfg, *args)


if __name__ == "__main__":
    cli()
