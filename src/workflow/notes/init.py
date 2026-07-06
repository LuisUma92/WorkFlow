"""Workspace initialization for WorkFlow Zettelkasten system.

Single-vault model: all Markdown notes live in 0000AV-Vault/.
Project directories (0010MC-, 0040EM-, etc.) are LaTeX output only.
One slipbox.db at the workspace root indexes all notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workflow.db.engine import init_local_db

__all__ = [
    "InitResult",
    "init_workspace",
    "VAULT_NAME",
]

VAULT_NAME = "0000AV-Vault"


@dataclass(frozen=True)
class InitResult:
    """Result of workspace initialization."""

    workspace_dir: Path
    directories_created: tuple[str, ...]
    already_existed: tuple[str, ...]
    warnings: tuple[str, ...]


def init_workspace(workspace_dir: Path) -> InitResult:
    """Initialize a WorkFlow workspace directory.

    Single-vault model:
    - .workflow/config.yaml (workspace marker)
    - 0000AV-Vault/inbox/ (fleeting notes landing zone)
    - 0000AV-Vault/templates/ (note templates)
    - slipbox.db at workspace root (single DB for all notes)

    Does NOT create per-project notes/ directories.
    Project directories are LaTeX output only.

    Idempotent -- safe to run on existing workspace.
    """
    dirs_created: list[str] = []
    already_existed: list[str] = []
    warnings: list[str] = []

    # Create workspace marker
    workflow_dir = workspace_dir / ".workflow"
    if not workflow_dir.exists():
        workflow_dir.mkdir(parents=True)
        dirs_created.append(".workflow/")
        config = workflow_dir / "config.yaml"
        config.write_text(
            f"workspace: {workspace_dir}\n"
            f"vault: {VAULT_NAME}\n"
            f"version: 2\n"
        )
    else:
        already_existed.append(".workflow/")

    # Create central vault
    vault = workspace_dir / VAULT_NAME
    inbox = vault / "inbox"
    templates = vault / "templates"

    for d in [vault, inbox, templates]:
        rel = str(d.relative_to(workspace_dir)) + "/"
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            dirs_created.append(rel)
        else:
            already_existed.append(rel)

    # Create note templates
    _create_note_templates(templates)

    # Create single slipbox.db at workspace root
    slipbox = workspace_dir / "slipbox.db"
    if not slipbox.exists():
        init_local_db(project_root=workspace_dir)
        dirs_created.append("slipbox.db")
    else:
        already_existed.append("slipbox.db")

    return InitResult(
        workspace_dir=workspace_dir,
        directories_created=tuple(dirs_created),
        already_existed=tuple(already_existed),
        warnings=tuple(warnings),
    )


def _create_note_templates(templates_dir: Path) -> None:
    """Create default note template files."""
    permanent = templates_dir / "permanent.md"
    if not permanent.exists():
        permanent.write_text(
            "---\n"
            "id: \n"
            "title: \n"
            "aliases: []\n"
            "type: permanent\n"
            "created: \n"
            "tags: []\n"
            "concepts: []\n"
            "references: []\n"
            "exercises: []\n"
            "images: []\n"
            "main_topic: \n"
            "discipline_area: \n"
            "relations:\n"
            "  derived_from: []\n"
            "  links: []\n"
            "entry_point: false\n"
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
            "aliases: []\n"
            "type: literature\n"
            "bibkey: \n"
            "origin: \n"
            "created: \n"
            "tags: []\n"
            "concepts: []\n"
            "references: []\n"
            "exercises: []\n"
            "images: []\n"
            "main_topic: \n"
            "discipline_area: \n"
            "relations:\n"
            "  derived_from: []\n"
            "  links: []\n"
            "entry_point: false\n"
            "---\n\n"
            "```bib\n"
            "% paste the biblatex entry here, then run :WorkflowBibImport\n"
            "```\n\n"
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
            "aliases: []\n"
            "type: fleeting\n"
            "created: \n"
            "tags: []\n"
            "---\n\n"
        )
