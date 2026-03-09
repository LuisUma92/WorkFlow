"""
Minimal config.yaml I/O.

config.yaml is now just a pointer to the DB record:

    project_type: lecture   # or "general"
    project_id: 42
"""

from pathlib import Path
from typing import Union

from itep.utils import load_yaml, write_yaml
from itep.database import (
    LectureInstance,
    GeneralProject,
    get_session,
)


def save_config(
    project_type: str,
    project_id: int,
    path: Union[str, Path],
) -> None:
    """Write a minimal config.yaml that points to a DB record."""
    data = {
        "project_type": project_type,
        "project_id": project_id,
    }
    write_yaml(Path(path), data)


def load_config(file: Union[str, Path]):
    """Read config.yaml, resolve the project from the DB, return it."""
    cfg = load_yaml(file)
    project_type = cfg["project_type"]
    project_id = cfg["project_id"]

    session = get_session()
    if project_type == "lecture":
        project = session.get(LectureInstance, project_id)
    elif project_type == "general":
        project = session.get(GeneralProject, project_id)
    else:
        raise ValueError(f"Unknown project_type: {project_type}")

    if project is None:
        raise ValueError(
            f"No {project_type} project with id={project_id} found in DB."
        )
    return project


def read_pointer(file: Union[str, Path]) -> dict:
    """Read just the raw config.yaml dict (project_type + project_id)."""
    return load_yaml(file)
