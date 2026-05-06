# src/latexzettel/infra/orm.py
"""
Shim de compatibilidad: re-exporta desde workflow.db (SQLAlchemy).

ITEP-0011 P3: el shim ahora apunta a la base de datos GLOBAL — las
tablas de notas (Note, Citation, Label, Link, Tag, NoteTag) viven en
``~/.local/share/workflow/workflow.db`` (GlobalBase), no en un
``slipbox.db`` por proyecto.

Interfaz expuesta:
  - get_engine()        — engine SQLAlchemy de la global workflow.db
  - Note, Citation, …   — modelos SQLAlchemy
  - create_all_tables() — crea las tablas globales (idempotente)
"""

from __future__ import annotations

import functools

from workflow.db.engine import get_global_engine, init_global_db
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
    """Lazily create and cache the GLOBAL DB engine (ITEP-0011 P3).

    Engine points at ~/.local/share/workflow/workflow.db. Use
    get_engine.cache_clear() to reset for tests.
    """
    return get_global_engine()


def create_all_tables() -> None:
    """Crea todas las tablas GlobalBase en el engine global (idempotente)."""
    init_global_db(engine=get_engine())


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
