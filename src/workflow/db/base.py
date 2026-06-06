"""
Two DeclarativeBase classes for the WorkFlow dual-database architecture.

- GlobalBase: tables in ~/.local/share/workflow/workflow.db  (XDG data dir; override via $WORKFLOW_DATA_DIR)
- LocalBase:  tables in <project>/slipbox.db            (project-level notes)
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class GlobalBase(DeclarativeBase):
    """Base for all tables stored in the global workflow.db."""
    pass


class LocalBase(DeclarativeBase):
    """Base for all tables stored in a project's slipbox.db."""
    pass
