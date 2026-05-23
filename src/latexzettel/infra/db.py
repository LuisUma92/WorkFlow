# src/latexzettel/infra/db.py
"""
Capa de infraestructura para base de datos (SQLAlchemy).

LZK-0004: API pública sin parámetro db — accede directamente al engine global.

  - ensure_tables()           — verifica/crea tablas en la GlobalDB
  - ensure_schema_if_needed() — ídem, versión lazy para api/notes.py
  - DbHealth                  — dataclass de resultado
  - connect() / close()       — no-ops (SQLAlchemy gestiona el pool)
  - db_session                — context manager que envuelve Session de SQLAlchemy

Internamente usa workflow.db.engine (get_global_engine, init_global_db).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from workflow.db.engine import get_global_engine, init_global_db
from workflow.db.models.notes import Note

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
      True si se ejecutó init_global_db() durante ensure_tables().
    error:
      mensaje de error si ok=False.
    """

    ok: bool
    initialized: bool
    error: Optional[str] = None


# =============================================================================
# Helpers internos
# =============================================================================


def _schema_exists() -> bool:
    """
    Verifica si la tabla 'note' existe ejecutando una consulta mínima.
    """
    engine = get_global_engine()
    try:
        with Session(engine) as session:
            session.query(Note).limit(1).all()
        return True
    except OperationalError:
        return False


# =============================================================================
# API pública
# =============================================================================


def connect() -> None:
    """No-op: SQLAlchemy gestiona conexiones via pool automáticamente."""
    pass


def close() -> None:
    """No-op: SQLAlchemy gestiona conexiones via pool automáticamente."""
    pass


def schema_exists() -> bool:
    """Verifica si el esquema existe intentando una consulta mínima sobre Note."""
    return _schema_exists()


def ensure_tables() -> DbHealth:
    """
    Garantiza que las tablas existan:
    - Si ya existen: no hace nada y retorna initialized=False.
    - Si no existen: crea tablas y retorna initialized=True.
    """
    try:
        if _schema_exists():
            return DbHealth(ok=True, initialized=False)

        init_global_db(engine=get_global_engine())

        if _schema_exists():
            return DbHealth(ok=True, initialized=True)

        return DbHealth(
            ok=False,
            initialized=True,
            error="No se pudo verificar el esquema tras crear tablas.",
        )
    except Exception as e:
        return DbHealth(ok=False, initialized=False, error=str(e))


def ensure_schema_if_needed() -> None:
    """
    Solo crea tablas si el primer acceso básico falla por OperationalError
    (típicamente 'no such table').
    """
    try:
        engine = get_global_engine()
        with Session(engine) as session:
            session.query(Note).limit(1).all()
    except OperationalError:
        health = ensure_tables()
        if not health.ok:
            raise DomainError(f"DB no disponible: {health.error}")


# =============================================================================
# Context manager
# =============================================================================


class db_session:
    """
    Context manager que devuelve una SQLAlchemy Session abierta sobre la GlobalDB.

    Uso:
        from latexzettel.infra.db import db_session, ensure_tables

        ensure_tables()
        with db_session() as session:
            session.query(Note).all()
    """

    def __init__(self):
        self._session: Optional[Session] = None

    def __enter__(self) -> Session:
        self._session = Session(get_global_engine())
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
