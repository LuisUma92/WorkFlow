"""Tests for NoteEdge ORM model, upsert helper, and migration round-trip.

Phase 2.1 of ITEP-0013: note relation graph (DB schema only).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note(session: Session, zettel_id: str) -> Note:
    note = Note(filename=f"{zettel_id}.md", reference=zettel_id, zettel_id=zettel_id)
    session.add(note)
    session.flush()
    return note


# ---------------------------------------------------------------------------
# Model existence
# ---------------------------------------------------------------------------


def test_note_edge_table_exists(global_session):
    assert global_session.scalars(select(NoteEdge)).all() == []


# ---------------------------------------------------------------------------
# Valid inserts
# ---------------------------------------------------------------------------


def test_note_edge_structural_insert(global_session):
    src = _make_note(global_session, "src-struct")
    tgt = _make_note(global_session, "tgt-struct")
    global_session.add(NoteEdge(
        source_id=src.id,
        target_id=tgt.id,
        target_zettel_id="tgt-struct",
        edge_class="structural",
        relation_type="continuation",
    ))
    global_session.flush()

    e = global_session.scalars(select(NoteEdge)).first()
    assert e is not None
    assert e.source_id == src.id
    assert e.target_id == tgt.id
    assert e.edge_class == "structural"
    assert e.relation_type == "continuation"
    assert e.weight == 1.0
    assert e.created_at is not None


def test_note_edge_associative_insert(global_session):
    src = _make_note(global_session, "src-assoc")
    global_session.add(NoteEdge(
        source_id=src.id,
        target_zettel_id="other-note",
        edge_class="associative",
        relation_type="see_also",
        rationale="Related concept",
    ))
    global_session.flush()

    e = global_session.scalars(select(NoteEdge)).first()
    assert e.edge_class == "associative"
    assert e.relation_type == "see_also"
    assert e.rationale == "Related concept"


def test_note_edge_unresolved_target(global_session):
    """target_id=None + target_zettel_id set is valid (unresolved edge)."""
    src = _make_note(global_session, "src-unresolved")
    global_session.add(NoteEdge(
        source_id=src.id,
        target_id=None,
        target_zettel_id="future-note",
        edge_class="structural",
        relation_type="refines",
    ))
    global_session.flush()

    e = global_session.scalars(select(NoteEdge)).first()
    assert e.target_id is None
    assert e.target_zettel_id == "future-note"


# ---------------------------------------------------------------------------
# Constraint violations (each test uses its own session to avoid poisoning)
# ---------------------------------------------------------------------------


def test_note_edge_invalid_edge_class_rejected(global_engine):
    with Session(global_engine) as session:
        src = _make_note(session, "src-bad-class")
        session.add(NoteEdge(
            source_id=src.id,
            target_zettel_id="tgt",
            edge_class="INVALID",
            relation_type="continuation",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_note_edge_invalid_relation_type_rejected(global_engine):
    with Session(global_engine) as session:
        src = _make_note(session, "src-bad-rel")
        session.add(NoteEdge(
            source_id=src.id,
            target_zettel_id="tgt",
            edge_class="structural",
            relation_type="UNKNOWN",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


def test_note_edge_unique_constraint(global_engine):
    with Session(global_engine) as session:
        src = _make_note(session, "src-dup")
        session.add(NoteEdge(
            source_id=src.id,
            target_zettel_id="same-target",
            edge_class="structural",
            relation_type="continuation",
        ))
        session.flush()
        session.add(NoteEdge(
            source_id=src.id,
            target_zettel_id="same-target",
            edge_class="structural",
            relation_type="continuation",
        ))
        with pytest.raises(IntegrityError):
            session.flush()


# ---------------------------------------------------------------------------
# upsert_note_edge
# ---------------------------------------------------------------------------


def test_upsert_note_edge_creates(global_session):
    from workflow.notes.linker_ops import upsert_note_edge

    src = _make_note(global_session, "src-upsert")
    created = upsert_note_edge(
        global_session,
        source_id=src.id,
        target_zettel_id="target-upsert",
        edge_class="associative",
        relation_type="supports",
    )
    assert created is True
    assert global_session.scalars(select(NoteEdge)).first() is not None


def test_upsert_note_edge_idempotent(global_session):
    from workflow.notes.linker_ops import upsert_note_edge

    src = _make_note(global_session, "src-idem")
    upsert_note_edge(
        global_session,
        source_id=src.id,
        target_zettel_id="target-idem",
        edge_class="associative",
        relation_type="supports",
    )
    created_second = upsert_note_edge(
        global_session,
        source_id=src.id,
        target_zettel_id="target-idem",
        edge_class="associative",
        relation_type="supports",
    )
    assert created_second is False
    assert len(global_session.scalars(select(NoteEdge)).all()) == 1


# ---------------------------------------------------------------------------
# Migration round-trip
# ---------------------------------------------------------------------------


def test_migration_round_trip():
    """Apply 0007 on a bare engine; verify table, indexes, and CHECK constraints."""
    import sqlite3

    repo_root = Path(__file__).resolve().parents[3]
    migration_path = repo_root / "src/workflow/db/migrations/global/0007_add_note_edges.py"
    spec = importlib.util.spec_from_file_location("m0007_add_note_edges", migration_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE note (id INTEGER PRIMARY KEY, "
            "filename TEXT NOT NULL UNIQUE, reference TEXT NOT NULL UNIQUE)"
        )
        m.upgrade(conn)

        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "note_edge" in tables

        indexes = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='note_edge'"
            ).fetchall()
        }
        assert "ix_note_edge_source" in indexes
        assert "ix_note_edge_target" in indexes
        assert "ix_note_edge_unresolved" in indexes

        # Seed a note row so FKs are satisfied
        conn.exec_driver_sql(
            "INSERT INTO note (id, filename, reference) VALUES (1, 'a.md', 'a')"
        )

        # Valid insert must succeed
        conn.exec_driver_sql(
            "INSERT INTO note_edge (source_id, target_zettel_id, edge_class, "
            "relation_type) VALUES (1, 'tgt', 'structural', 'continuation')"
        )

        # Invalid edge_class must be rejected by CHECK constraint
        with pytest.raises(Exception, match="CHECK"):
            conn.exec_driver_sql(
                "INSERT INTO note_edge (source_id, target_zettel_id, edge_class, "
                "relation_type) VALUES (1, 'tgt2', 'INVALID', 'continuation')"
            )

        # Invalid relation_type must be rejected by CHECK constraint
        with pytest.raises(Exception, match="CHECK"):
            conn.exec_driver_sql(
                "INSERT INTO note_edge (source_id, target_zettel_id, edge_class, "
                "relation_type) VALUES (1, 'tgt3', 'structural', 'UNKNOWN')"
            )


# ---------------------------------------------------------------------------
# Live-table drift regression (production bug, Wave 0 D2 backfill 2026-07-05)
#
# The deployed note_edge table was created by SQLAlchemy metadata.create_all()
# *before* server_default=text("CURRENT_TIMESTAMP") was added to the model.
# Migration 0007's CREATE TABLE is idempotent (skips if the table already
# exists) so it never retrofit the missing DEFAULT onto that live table.
# created_at is therefore NOT NULL with *no* default at the DDL level there —
# an ORM insert that omits created_at relies entirely on a Python-side
# default now. This test builds that exact DDL (copied from migration 0007
# verbatim, minus "DEFAULT CURRENT_TIMESTAMP") to reproduce it.
# ---------------------------------------------------------------------------


def test_note_edge_insert_against_table_without_server_default():
    """ORM insert must supply created_at itself; DB-level default cannot be relied on."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE note (id INTEGER PRIMARY KEY, "
            "filename TEXT NOT NULL UNIQUE, reference TEXT NOT NULL UNIQUE)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE note_edge (
                id              INTEGER PRIMARY KEY,
                source_id       INTEGER NOT NULL
                                    REFERENCES note(id) ON DELETE CASCADE,
                target_id       INTEGER
                                    REFERENCES note(id) ON DELETE SET NULL,
                target_zettel_id VARCHAR(21) NOT NULL,
                edge_class      VARCHAR(16) NOT NULL,
                relation_type   VARCHAR(24) NOT NULL,
                weight          REAL NOT NULL DEFAULT 1.0,
                rationale       TEXT,
                created_at      DATETIME NOT NULL,
                CONSTRAINT ck_note_edge_class_valid
                    CHECK (edge_class IN ('structural', 'associative')),
                CONSTRAINT ck_note_edge_relation_type_valid
                    CHECK (relation_type IN (
                        'continuation', 'refines', 'branches', 'synthesis', 'rebuttal',
                        'supports', 'contradicts', 'expands', 'see_also'
                    )),
                CONSTRAINT uq_note_edge_src_tgt_rel
                    UNIQUE (source_id, target_zettel_id, relation_type)
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO note (id, filename, reference) VALUES (1, 'a.md', 'a')"
        )

    with Session(engine) as session:
        session.add(NoteEdge(
            source_id=1,
            target_zettel_id="tgt-live-ddl",
            edge_class="structural",
            relation_type="continuation",
        ))
        session.flush()

        e = session.scalars(select(NoteEdge)).first()
        assert e is not None
        assert e.created_at is not None
