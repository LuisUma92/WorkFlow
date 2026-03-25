# src/latexzettel/infra/db.py
"""
Capa de infraestructura para base de datos (SQLAlchemy).

Mantiene la misma API pública que la versión Peewee para que los 7 módulos
API que importan de aquí no necesiten cambios:

  - ensure_tables(db)           — usado por cli/main.py, server/main.py,
                                   api/render.py, api/analysis.py,
                                   api/markdown.py, api/sync.py
  - ensure_schema_if_needed(db) — usado por api/notes.py
  - DbHealth                    — dataclass de resultado
  - connect(db) / close(db)     — no-ops (SQLAlchemy gestiona el pool)
  - db_session                  — context manager que envuelve Session de SQLAlchemy

Internamente usa workflow.db.engine para crear el engine/sesión local.
El parámetro `db` que reciben las funciones es el módulo orm de latexzettel
(latexzettel.infra.orm), que ahora actúa como shim y expone:
  - db.engine            — SQLAlchemy engine
  - db.Note              — clase SQLAlchemy Note (de workflow.db.models.notes)
  - db.create_all_tables() — crea tablas via LocalBase.metadata.create_all
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from latexzettel.domain.errors import DomainError


# =============================================================================
# Configuración
# =============================================================================


@dataclass(frozen=True)
class DbHealth:
    """
    Estado de salud/inicialización del esquema.

    ok:
      True si el esquema está disponible para operar.
    initialized:
      True si se ejecutó create_all_tables() durante ensure_tables().
    error:
      mensaje de error si ok=False.
    """

    ok: bool
    initialized: bool
    error: Optional[str] = None


# =============================================================================
# Helpers internos
# =============================================================================


def _get_engine(db: Any):
    """Extrae el engine SQLAlchemy del módulo orm."""
    return db.engine


def _schema_exists(db: Any) -> bool:
    """
    Verifica si la tabla 'note' existe ejecutando una consulta mínima.
    """
    engine = _get_engine(db)
    try:
        with Session(engine) as session:
            session.query(db.Note).limit(1).all()
        return True
    except OperationalError:
        return False


# =============================================================================
# API pública (mismas firmas que la versión Peewee)
# =============================================================================


def connect(_db: Any) -> None:
    """
    No-op: SQLAlchemy gestiona conexiones via pool automáticamente.
    Se mantiene por compatibilidad con código existente.
    """
    pass


def close(_db: Any) -> None:
    """
    No-op: SQLAlchemy gestiona conexiones via pool automáticamente.
    Se mantiene por compatibilidad con código existente.
    """
    pass


def schema_exists(db: Any) -> bool:
    """
    Verifica si el esquema existe intentando una consulta mínima sobre Note.
    """
    return _schema_exists(db)


def ensure_tables(db: Any) -> DbHealth:
    """
    Garantiza que las tablas existan:
    - Si ya existen: no hace nada y retorna initialized=False.
    - Si no existen: crea tablas y retorna initialized=True.
    """
    try:
        if _schema_exists(db):
            return DbHealth(ok=True, initialized=False)

        db.create_all_tables()

        if _schema_exists(db):
            return DbHealth(ok=True, initialized=True)

        return DbHealth(
            ok=False,
            initialized=True,
            error="No se pudo verificar el esquema tras crear tablas.",
        )
    except Exception as e:
        return DbHealth(ok=False, initialized=False, error=str(e))


def ensure_schema_if_needed(db: Any) -> None:
    """
    Solo crea tablas si el primer acceso básico falla por OperationalError
    (típicamente 'no such table').
    """
    try:
        engine = _get_engine(db)
        with Session(engine) as session:
            session.query(db.Note).limit(1).all()
    except OperationalError:
        health = ensure_tables(db)
        if not health.ok:
            raise DomainError(f"DB no disponible: {health.error}")


# =============================================================================
# Context manager
# =============================================================================


class db_session:
    """
    Context manager que devuelve una SQLAlchemy Session abierta.

    Uso:
        from latexzettel.infra import orm as db_mod
        from latexzettel.infra.db import db_session, ensure_tables

        ensure_tables(db_mod)
        with db_session(db_mod) as session:
            session.query(db_mod.Note).all()
    """

    def __init__(self, db: Any):
        self._db = db
        self._session: Optional[Session] = None

    def __enter__(self) -> Session:
        engine = _get_engine(self._db)
        self._session = Session(engine)
        return self._session

    def __exit__(self, exc_type, _exc, _tb) -> bool:
        if self._session is not None:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
            self._session.close()
            self._session = None
        return False
