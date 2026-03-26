"""
Engine and session factories for the WorkFlow dual-database architecture.

Global DB: ~/.local/share/workflow/workflow.db   (via appdirs)
Local DB:  <project_root>/slipbox.db
"""

from __future__ import annotations

from pathlib import Path

from appdirs import user_data_dir
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from workflow.db.base import GlobalBase, LocalBase

__all__ = [
    "get_global_engine",
    "get_local_engine",
    "get_global_session",
    "get_local_session",
    "init_global_db",
    "init_local_db",
]

# ── Helpers ────────────────────────────────────────────────────────────────


def _enable_fk_pragma(dbapi_conn, _connection_record):
    """Enable foreign-key enforcement for every SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _default_global_path() -> Path:
    data_dir = Path(user_data_dir("workflow", "LuisUmana"))
    return data_dir / "workflow.db"


# ── Engine factories ───────────────────────────────────────────────────────


def get_global_engine(db_path: Path | None = None, echo: bool = False):
    """Return an SQLAlchemy engine bound to the global workflow.db."""
    if db_path is None:
        db_path = _default_global_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    event.listen(engine, "connect", _enable_fk_pragma)
    return engine


def get_local_engine(project_root: Path, echo: bool = False):
    """Return an SQLAlchemy engine bound to <project_root>/slipbox.db."""
    db_path = Path(project_root) / "slipbox.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    event.listen(engine, "connect", _enable_fk_pragma)
    return engine


# ── Session factories ──────────────────────────────────────────────────────


def get_global_session(engine=None) -> Session:
    """Return a new session for the global database."""
    if engine is None:
        engine = get_global_engine()
    factory = sessionmaker(bind=engine)
    return factory()


def get_local_session(engine=None, project_root: Path | None = None) -> Session:
    """Return a new session for a project-local slipbox database."""
    if engine is None:
        if project_root is None:
            raise ValueError("Provide either engine or project_root.")
        engine = get_local_engine(project_root)
    factory = sessionmaker(bind=engine)
    return factory()


# ── Initialisation helpers ─────────────────────────────────────────────────


def _ensure_models_loaded():
    """Import model modules so GlobalBase/LocalBase metadata is populated."""
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.project  # noqa: F401
    import workflow.db.models.notes  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401


def init_global_db(engine=None):
    """Create all GlobalBase tables in the global database."""
    _ensure_models_loaded()
    if engine is None:
        engine = get_global_engine()
    GlobalBase.metadata.create_all(engine)
    return engine


def init_local_db(engine=None, project_root: Path | None = None):
    """Create all LocalBase tables in a project-local slipbox database."""
    _ensure_models_loaded()
    if engine is None:
        if project_root is None:
            raise ValueError("Provide either engine or project_root.")
        engine = get_local_engine(project_root)
    LocalBase.metadata.create_all(engine)
    return engine
