"""
This manager manages de CUDA operations for the strc.ProjectStructure
"""

import itep.structure as strc
from itep.utils import gather_input, select_enum_type, ensure_dir

from pathlib import Path
from typing import Optional, List, Tuple
from datetime import date


def set_project_type(ps: strc.ProjectStructure) -> strc.ProjectStructure:
    ps.project_type = select_enum_type("project type", strc.ProjectType)
    return ps


def restart_metadata(ps: strc.ProjectStructure) -> strc.ProjectStructure:
    parent_dir = Path.cwd().absolute()
    print(f"Your current workin directory has path:\n\t>> {parent_dir}")
    ans = gather_input(
        "Do you want to use it as projects parent path? (y/n): ",
        "^[yn]{1}",
    )
    if ans == "n":
        parent_dir = Path(
            gather_input(
                "Enter your parent path",
                "^[A-Za-z0-9/_-.()[]{}']",
            )
        )
        ensure_dir(parent_dir, "parent directory")
    data = strc.MetaData(abs_parent_dir=parent_dir)
    ps.data = data
    return ps
