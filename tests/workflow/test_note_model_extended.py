"""
TDD tests for Phase 7b — Extended Note model with Zettelkasten fields.

Tests are written FIRST (RED), then the model is extended to pass them (GREEN).
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from workflow.db.base import LocalBase
from workflow.db.models.notes import Note
from workflow.db.repos.sqlalchemy import SqlNoteRepo


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    LocalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def repo(db_session):
    return SqlNoteRepo(db_session)


# ---------------------------------------------------------------------------
# Model field tests
# ---------------------------------------------------------------------------


def test_note_with_zettel_id(db_session):
    """Note can store all new Zettelkasten fields."""
    note = Note(
        filename="gauss.tex",
        reference="ref-gauss",
        zettel_id="20260326-gauss-law",
        title="Gauss's Law",
        note_type="permanent",
        source_format="md",
    )
    db_session.add(note)
    db_session.commit()

    loaded = db_session.get(Note, note.id)
    assert loaded.zettel_id == "20260326-gauss-law"
    assert loaded.title == "Gauss's Law"
    assert loaded.note_type == "permanent"
    assert loaded.source_format == "md"


def test_note_zettel_id_unique(db_session):
    """zettel_id must be unique across notes."""
    note1 = Note(filename="a.tex", reference="ref-a", zettel_id="20260326-gauss-law")
    note2 = Note(filename="b.tex", reference="ref-b", zettel_id="20260326-gauss-law")
    db_session.add(note1)
    db_session.commit()

    db_session.add(note2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_note_backward_compatible(db_session):
    """New fields are nullable — old-style notes still work."""
    note = Note(filename="old.tex", reference="old-ref")
    db_session.add(note)
    db_session.commit()

    loaded = db_session.get(Note, note.id)
    assert loaded.zettel_id is None
    assert loaded.title is None
    assert loaded.note_type is None
    assert loaded.source_format is None


def test_note_type_values(db_session):
    """note_type accepts permanent, literature, and fleeting."""
    for ntype in ("permanent", "literature", "fleeting"):
        note = Note(
            filename=f"{ntype}.tex",
            reference=f"ref-{ntype}",
            note_type=ntype,
        )
        db_session.add(note)
    db_session.commit()

    from sqlalchemy import select
    stmt = select(Note).where(Note.note_type.in_(["permanent", "literature", "fleeting"]))
    results = list(db_session.scalars(stmt).all())
    assert len(results) == 3


# ---------------------------------------------------------------------------
# Repository method tests
# ---------------------------------------------------------------------------


def test_find_by_zettel_id(db_session, repo):
    """SqlNoteRepo.find_by_zettel_id returns the correct note."""
    note = Note(
        filename="maxwell.tex",
        reference="ref-maxwell",
        zettel_id="20260326-maxwell-equations",
        title="Maxwell's Equations",
        note_type="permanent",
        source_format="tex",
    )
    db_session.add(note)
    db_session.commit()

    found = repo.find_by_zettel_id("20260326-maxwell-equations")
    assert found is not None
    assert found.title == "Maxwell's Equations"


def test_find_by_zettel_id_missing(db_session, repo):
    """find_by_zettel_id returns None when zettel_id not found."""
    result = repo.find_by_zettel_id("nonexistent-id")
    assert result is None


def test_find_by_type(db_session, repo):
    """SqlNoteRepo.find_by_type filters by note_type correctly."""
    db_session.add(Note(filename="p1.tex", reference="rp1", note_type="permanent"))
    db_session.add(Note(filename="p2.tex", reference="rp2", note_type="permanent"))
    db_session.add(Note(filename="l1.tex", reference="rl1", note_type="literature"))
    db_session.add(Note(filename="f1.tex", reference="rf1", note_type="fleeting"))
    db_session.commit()

    permanents = repo.find_by_type("permanent")
    assert len(permanents) == 2
    assert all(n.note_type == "permanent" for n in permanents)

    literature = repo.find_by_type("literature")
    assert len(literature) == 1

    fleeting = repo.find_by_type("fleeting")
    assert len(fleeting) == 1


def test_find_by_type_empty(db_session, repo):
    """find_by_type returns empty list when no notes match."""
    result = repo.find_by_type("permanent")
    assert result == []
