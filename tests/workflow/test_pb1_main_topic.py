"""Phase B.1 — note.main_topic_id FK + frontmatter fields."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import init_global_db
import workflow.db.models.academic  # noqa: F401
import workflow.db.models.notes  # noqa: F401
from workflow.db.models.academic import DisciplineArea, MainTopic
from workflow.db.models.notes import Note
from workflow.validation.schemas import validate_note_frontmatter


def _enable_fk(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@pytest.fixture()
def global_engine(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path}/g.db")
    event.listen(eng, "connect", _enable_fk)
    init_global_db(eng)
    return eng


# ── ORM / migration ──────────────────────────────────────────────────────────


def test_migration_adds_column_and_index(global_engine):
    insp = inspect(global_engine)
    cols = {c["name"] for c in insp.get_columns("note")}
    assert "main_topic_id" in cols
    idx_names = {ix["name"] for ix in insp.get_indexes("note")}
    assert "ix_note_main_topic_id" in idx_names


def test_migration_idempotent(global_engine):
    """Re-applying the migration over an existing schema is a no-op."""
    from workflow.db.migrations import upgrade

    result = upgrade(global_engine, "global")
    assert "0006_note_main_topic_id" in result.skipped


def test_note_main_topic_relationship_round_trip(global_engine):
    with Session(global_engine) as session:
        da = DisciplineArea(
            code="FI0006",
            name="Mecánica",
            discipline_num=1,
            topic_num=6,
            area_initials="FI",
        )
        session.add(da)
        session.flush()
        mt = MainTopic(
            code="FI0006",
            name="Mecánica clásica",
            discipline_area_id=da.id,
        )
        session.add(mt)
        session.flush()

        note = Note(filename="n.md", reference="n", main_topic_id=mt.id)
        session.add(note)
        session.commit()

        fetched = session.query(Note).one()
        assert fetched.main_topic_id == mt.id
        assert fetched.main_topic.code == "FI0006"


def test_note_main_topic_fk_set_null_on_delete(global_engine):
    with Session(global_engine) as session:
        da = DisciplineArea(
            code="FI0007",
            name="Termo",
            discipline_num=1,
            topic_num=7,
            area_initials="FI",
        )
        session.add(da)
        session.flush()
        mt = MainTopic(code="FI0007", name="Termo", discipline_area_id=da.id)
        session.add(mt)
        session.flush()
        note = Note(filename="n2.md", reference="n2", main_topic_id=mt.id)
        session.add(note)
        session.commit()

        session.delete(mt)
        session.commit()

        refetched = session.query(Note).one()
        assert refetched.main_topic_id is None


# ── Frontmatter schema fields ────────────────────────────────────────────────


def _base_fm(**extra) -> dict:
    return {"id": "n-1", "title": "T", **extra}


def test_frontmatter_without_main_topic_validates_clean():
    fm, errs = validate_note_frontmatter(_base_fm())
    assert errs == []
    assert fm.main_topic is None
    assert fm.discipline_area is None


def test_frontmatter_with_main_topic_slug_parses():
    fm, errs = validate_note_frontmatter(_base_fm(main_topic="FI0006"))
    assert errs == []
    assert fm.main_topic == "FI0006"


def test_frontmatter_with_main_topic_int_id_parses():
    fm, errs = validate_note_frontmatter(_base_fm(main_topic=42))
    assert errs == []
    assert fm.main_topic == 42


def test_frontmatter_main_topic_invalid_type_errors():
    fm, errs = validate_note_frontmatter(_base_fm(main_topic=[1, 2]))
    assert fm is None
    assert any("main_topic" in e for e in errs)


def test_frontmatter_with_discipline_area_parses():
    fm, errs = validate_note_frontmatter(_base_fm(discipline_area="FI0006"))
    assert errs == []
    assert fm.discipline_area == "FI0006"


def test_frontmatter_discipline_area_bad_format_errors():
    fm, errs = validate_note_frontmatter(_base_fm(discipline_area="bad"))
    assert fm is None
    assert any("discipline_area" in e for e in errs)


def test_frontmatter_discipline_area_non_string_errors():
    fm, errs = validate_note_frontmatter(_base_fm(discipline_area=123))
    assert fm is None
    assert any("discipline_area" in e for e in errs)
