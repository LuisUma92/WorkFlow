"""ITEP-0011 P5 — ProjectNote + PrismaDecision LocalBase models (TDD)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workflow.db.base import LocalBase
from workflow.db.engine import init_local_db
from workflow.db.models.project_layer import ProjectNote, PrismaDecision


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def local_engine(tmp_path):
    """Fresh in-memory LocalBase for every test."""
    db_path = tmp_path / "slipbox.db"
    engine = create_engine(f"sqlite:///{db_path}")
    LocalBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(local_engine):
    with Session(local_engine) as s:
        yield s


# ── ProjectNote — model constraints ───────────────────────────────────────────


def test_project_note_create_idea(session):
    note = ProjectNote(kind="idea", body="Forces are vectors.")
    session.add(note)
    session.commit()
    assert note.id is not None
    assert note.kind == "idea"
    assert note.global_note_ref is None
    assert isinstance(note.created_at, datetime)


def test_project_note_create_hypothesis(session):
    note = ProjectNote(kind="hypothesis", body="Energy is conserved.")
    session.add(note)
    session.commit()
    assert note.kind == "hypothesis"


def test_project_note_create_connection(session):
    note = ProjectNote(kind="connection", body="Links newton to energy.")
    session.add(note)
    session.commit()
    assert note.kind == "connection"


def test_project_note_with_global_note_ref(session):
    note = ProjectNote(kind="idea", body="See vault note.", global_note_ref="202605220001")
    session.add(note)
    session.commit()
    assert note.global_note_ref == "202605220001"


def test_project_note_body_required(session):
    """NULL body must be rejected at the DB level."""
    session.add(ProjectNote(kind="idea", body=None))
    with pytest.raises(IntegrityError):
        session.commit()


def test_project_note_kind_required(session):
    """NULL kind must be rejected."""
    session.add(ProjectNote(kind=None, body="text"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_project_note_invalid_kind_rejected(local_engine):
    """CHECK constraint on kind enforced by SQLite."""
    with Session(local_engine) as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO project_note (kind, body, created_at) "
                    "VALUES ('bad_kind', 'x', datetime('now'))"
                )
            )
            s.commit()


def test_project_note_list_all(session):
    session.add_all([
        ProjectNote(kind="idea", body="A"),
        ProjectNote(kind="hypothesis", body="B"),
        ProjectNote(kind="connection", body="C"),
    ])
    session.commit()
    rows = session.query(ProjectNote).all()
    assert len(rows) == 3


# ── PrismaDecision — model constraints ────────────────────────────────────────


def test_prisma_decision_create_included(session):
    d = PrismaDecision(bibkey="smith2020", decision="included")
    session.add(d)
    session.commit()
    assert d.id is not None
    assert d.bibkey == "smith2020"
    assert d.decision == "included"
    assert d.rationale is None
    assert d.reviewer is None


def test_prisma_decision_create_excluded_with_rationale(session):
    d = PrismaDecision(
        bibkey="jones2021",
        decision="excluded",
        rationale="Out of scope.",
        reviewer="luis",
    )
    session.add(d)
    session.commit()
    assert d.rationale == "Out of scope."
    assert d.reviewer == "luis"


def test_prisma_decision_uncertain(session):
    d = PrismaDecision(bibkey="anon2019", decision="uncertain")
    session.add(d)
    session.commit()
    assert d.decision == "uncertain"


def test_prisma_decision_bibkey_required(session):
    session.add(PrismaDecision(bibkey=None, decision="included"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_prisma_decision_decision_required(session):
    session.add(PrismaDecision(bibkey="x2020", decision=None))
    with pytest.raises(IntegrityError):
        session.commit()


def test_prisma_decision_invalid_decision_rejected(local_engine):
    with Session(local_engine) as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO prisma_decision (bibkey, decision) "
                    "VALUES ('x2020', 'maybe')"
                )
            )
            s.commit()


def test_prisma_decision_unique_bibkey_per_project(session):
    """Same bibkey can appear once (upsert semantics via unique constraint)."""
    session.add(PrismaDecision(bibkey="dup2020", decision="included"))
    session.commit()
    session.add(PrismaDecision(bibkey="dup2020", decision="excluded"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_prisma_decision_reviewed_at_nullable(session):
    d = PrismaDecision(bibkey="y2022", decision="included", reviewed_at=None)
    session.add(d)
    session.commit()
    assert d.reviewed_at is None


# ── Migration ─────────────────────────────────────────────────────────────────


def test_migration_creates_tables(tmp_path):
    """init_local_db runs migration 0002; both tables present afterwards."""
    engine = init_local_db(project_root=tmp_path)
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
    assert "project_note" in tables
    assert "prisma_decision" in tables
    engine.dispose()


def test_migration_idempotent(tmp_path):
    """Running init_local_db twice does not raise."""
    init_local_db(project_root=tmp_path)
    init_local_db(project_root=tmp_path)
