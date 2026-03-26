"""Workspace initialization for WorkFlow Zettelkasten projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workflow.db.engine import init_local_db

__all__ = [
    "InitResult",
    "init_workspace",
]

# Special two-letter suffixes for 00XX directories that should be skipped
_SPECIAL_SUFFIXES = {"AA", "BB", "EE", "II", "ZZ"}


@dataclass(frozen=True)
class InitResult:
    """Result of workspace initialization."""

    workspace_dir: Path
    projects_initialized: tuple[str, ...]
    directories_created: tuple[str, ...]
    already_existed: tuple[str, ...]
    warnings: tuple[str, ...]


def init_workspace(workspace_dir: Path) -> InitResult:
    """Initialize a WorkFlow workspace directory.

    Creates:
    - .workflow/config.yaml (workspace marker)
    - 00ZZ-Vault/inbox/ (global triage zone for fleeting notes)
    - 00ZZ-Vault/templates/ (note templates)
    - For each existing project directory (matches [0-9]*-*/ pattern):
      - notes/ subdirectory (Markdown vault)
      - slipbox.db (if not exists)

    Idempotent — safe to run on existing workspace.
    """
    dirs_created: list[str] = []
    already_existed: list[str] = []
    projects_init: list[str] = []
    warnings: list[str] = []

    # Create workspace marker
    workflow_dir = workspace_dir / ".workflow"
    if not workflow_dir.exists():
        workflow_dir.mkdir(parents=True)
        dirs_created.append(".workflow/")
        config = workflow_dir / "config.yaml"
        config.write_text(f"workspace: {workspace_dir}\nversion: 1\n")
    else:
        already_existed.append(".workflow/")

    # Create global vault
    vault = workspace_dir / "00ZZ-Vault"
    inbox = vault / "inbox"
    templates = vault / "templates"

    for d in [vault, inbox, templates]:
        rel = str(d.relative_to(workspace_dir)) + "/"
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            dirs_created.append(rel)
        else:
            already_existed.append(rel)

    # Create note templates if they don't exist
    _create_note_templates(templates)

    # Initialize project directories
    for entry in sorted(workspace_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        # Must start with a digit and contain a hyphen
        if not name[0].isdigit() or "-" not in name:
            continue
        # Skip special 00XX directories
        if _is_special_dir(name):
            continue

        # This is a project directory — initialize notes/
        notes_dir = entry / "notes"
        rel = f"{name}/notes/"
        if not notes_dir.exists():
            notes_dir.mkdir()
            dirs_created.append(rel)
        else:
            already_existed.append(rel)

        # Create slipbox.db if not exists
        slipbox = entry / "slipbox.db"
        if not slipbox.exists():
            init_local_db(project_root=entry)
            projects_init.append(name)

    return InitResult(
        workspace_dir=workspace_dir,
        projects_initialized=tuple(projects_init),
        directories_created=tuple(dirs_created),
        already_existed=tuple(already_existed),
        warnings=tuple(warnings),
    )


def _is_special_dir(name: str) -> bool:
    """Return True if this is a special 00XX- directory that should be skipped."""
    if not name.startswith("00"):
        return False
    # Check the two characters after "00"
    suffix = name[2:4]
    return suffix in _SPECIAL_SUFFIXES


def _create_note_templates(templates_dir: Path) -> None:
    """Create default note template files."""
    permanent = templates_dir / "permanent.md"
    if not permanent.exists():
        permanent.write_text(
            "---\n"
            "id: \n"
            "title: \n"
            "type: permanent\n"
            "created: \n"
            "tags: []\n"
            "concepts: []\n"
            "---\n\n"
            "## Summary\n\n"
            "## Key ideas\n\n"
            "## Connections\n"
        )

    literature = templates_dir / "literature.md"
    if not literature.exists():
        literature.write_text(
            "---\n"
            "id: \n"
            "title: \n"
            "type: literature\n"
            "bibkey: \n"
            "created: \n"
            "tags: []\n"
            "---\n\n"
            "## Key ideas\n\n"
            "## Chapter notes\n\n"
            "## Questions raised\n\n"
            "## Connections\n"
        )

    fleeting = templates_dir / "fleeting.md"
    if not fleeting.exists():
        fleeting.write_text(
            "---\n"
            "id: \n"
            "title: \n"
            "type: fleeting\n"
            "created: \n"
            "tags: []\n"
            "---\n\n"
        )
