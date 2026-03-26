# src/latexzettel/infra/orm.py
"""
Shim de compatibilidad: re-exporta desde workflow.db (SQLAlchemy).

Este módulo expone la interfaz que espera infra/db.py y los callers
existentes (cli/main.py, server/main.py):

  - engine              — SQLAlchemy engine para slipbox.db local
  - Note                — modelo SQLAlchemy Note
  - create_all_tables() — crea todas las tablas LocalBase en el engine

El engine se crea apuntando al directorio de trabajo actual (cwd).
Para proyectos que especifican --root, server/main.py y cli/main.py
pueden reemplazar este módulo con uno configurado adecuadamente, pero
para uso por defecto '.' es el comportamiento legacy que preservamos.
"""

from __future__ import annotations

import functools
from pathlib import Path

from workflow.db.engine import get_local_engine, init_local_db
from workflow.db.models.notes import (  # noqa: F401
    Citation,
    Label,
    Link,
    Note,
    NoteTag,
    Tag,
)


@functools.lru_cache(maxsize=1)
def get_engine():
    """Lazily create and cache the local DB engine.

    Note: Path(".") is resolved at first-call time. The engine is cached
    for the process lifetime — CWD must be stable before the first call.
    Use get_engine.cache_clear() to reset if needed (e.g., in tests).
    """
    return get_local_engine(project_root=Path("."))


def create_all_tables() -> None:
    """Crea todas las tablas LocalBase en el engine local."""
    init_local_db(engine=get_engine())


__all__ = [
    "get_engine",
    "Note",
    "Citation",
    "Label",
    "Link",
    "Tag",
    "NoteTag",
    "create_all_tables",
]
