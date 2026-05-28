"""Phase 4D — notes link --main-topic materializes Note.main_topic_id FK.

Tests:
- link_main_topic service helper: rewrites frontmatter, writes FK
- --remove drops key and clears FK
- --strict errors on unknown slug
- lenient miss warns but does NOT write
- CLI integration: --main-topic, --remove, --strict flags
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

import workflow.db.models.academic  # noqa: F401
import workflow.db.models.bibliography  # noqa: F401
import workflow.db.models.exercises  # noqa: F401
import workflow.db.models.notes  # noqa: F401
import workflow.db.models.project  # noqa: F401
from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.notes import Note
from workflow.notes.cli import notes
from workflow.notes.service import NoteNotFound, NoteValidationError, add_link


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_note(directory: Path, note_id: str, title: str = "Test", **kwargs) -> Path:
    fm: dict = {
        "id": note_id,
        "title": title,
        "type": kwargs.get("type", "permanent"),
        "tags": list(kwargs.get("tags", [])),
        "concepts": list(kwargs.get("concepts", [])),
        "references": list(kwargs.get("references", [])),
        "exercises": list(kwargs.get("exercises", [])),
        "images": [],
    }
    if "main_topic" in kwargs:
        fm["main_topic"] = kwargs["main_topic"]
    body = kwargs.get("body", "## Body\n\nContent.\n")
    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n" + body
    path = directory / f"{note_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _make_engine() -> object:
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    return _make_engine()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def notes_dir(tmp_path):
    d = tmp_path / "notes"
    d.mkdir()
    return d


@pytest.fixture()
def seeded(session, notes_dir):
    """Seed one Note row + one MainTopic row; write .md file."""
    da = DisciplineArea(
        code="FI0002", name="Fisica", discipline_num=2, topic_num=1, area_initials="FI"
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code="FI0002", name="Mecanica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    note_row = Note(
        filename="note-mt01.md", reference="note-mt01", zettel_id="note-mt01"
    )
    session.add(note_row)
    session.commit()
    _write_note(notes_dir, "note-mt01", "MainTopic Link Test")
    return {"note": note_row, "main_topic": mt, "notes_dir": notes_dir}


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Service: add_link with main_topic kwarg
# ---------------------------------------------------------------------------


class TestAddLinkMainTopic:
    def test_link_main_topic_sets_frontmatter_key(self, session, seeded):
        d = seeded["notes_dir"]
        path, fm, issues = add_link(
            d, "note-mt01", main_topic="FI0002", session=session
        )
        assert issues == []
        assert fm.main_topic == "FI0002"

    def test_link_main_topic_writes_fk_in_db(self, session, seeded):
        d = seeded["notes_dir"]
        add_link(d, "note-mt01", main_topic="FI0002", session=session)
        session.flush()
        note_row = session.scalars(
            select(Note).where(Note.zettel_id == "note-mt01")
        ).one()
        assert note_row.main_topic_id == seeded["main_topic"].id

    def test_link_main_topic_idempotent(self, session, seeded):
        d = seeded["notes_dir"]
        add_link(d, "note-mt01", main_topic="FI0002", session=session)
        session.flush()
        add_link(d, "note-mt01", main_topic="FI0002", session=session)
        session.flush()
        note_row = session.scalars(
            select(Note).where(Note.zettel_id == "note-mt01")
        ).one()
        assert note_row.main_topic_id == seeded["main_topic"].id

    def test_link_main_topic_remove_drops_frontmatter_key(self, session, seeded):
        d = seeded["notes_dir"]
        add_link(d, "note-mt01", main_topic="FI0002", session=session)
        session.flush()
        path, fm, issues = add_link(
            d, "note-mt01", main_topic="FI0002", session=session, remove=True
        )
        session.flush()
        assert fm.main_topic is None

    def test_link_main_topic_remove_clears_fk(self, session, seeded):
        d = seeded["notes_dir"]
        add_link(d, "note-mt01", main_topic="FI0002", session=session)
        session.flush()
        add_link(d, "note-mt01", main_topic="FI0002", session=session, remove=True)
        session.flush()
        note_row = session.scalars(
            select(Note).where(Note.zettel_id == "note-mt01")
        ).one()
        assert note_row.main_topic_id is None

    def test_link_main_topic_remove_idempotent(self, session, seeded):
        d = seeded["notes_dir"]
        # Remove without prior link — should not error
        path, fm, issues = add_link(
            d, "note-mt01", main_topic="FI0002", session=session, remove=True
        )
        session.flush()
        assert fm.main_topic is None

    def test_link_main_topic_lenient_miss_no_write(self, session, seeded):
        d = seeded["notes_dir"]
        original = (d / "note-mt01.md").read_text()
        path, fm, issues = add_link(
            d, "note-mt01", main_topic="UNKN01", session=session, strict=False
        )
        # Frontmatter not modified
        assert fm.main_topic is None
        assert (d / "note-mt01.md").read_text() == original
        # Warning in issues
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"

    def test_link_main_topic_strict_miss_raises(self, session, seeded):
        d = seeded["notes_dir"]
        with pytest.raises(NoteValidationError):
            add_link(
                d, "note-mt01", main_topic="UNKN01", session=session, strict=True
            )
        # FK not set
        session.flush()
        note_row = session.scalars(
            select(Note).where(Note.zettel_id == "note-mt01")
        ).one()
        assert note_row.main_topic_id is None

    def test_link_main_topic_requires_synced_note(self, session, seeded):
        d = seeded["notes_dir"]
        _write_note(d, "unsynced-mt99", "Unsynced")
        with pytest.raises(NoteNotFound):
            add_link(d, "unsynced-mt99", main_topic="FI0002", session=session)

    def test_link_main_topic_without_session_writes_frontmatter_only(self, seeded):
        """Back-compat: no session → frontmatter-only path."""
        d = seeded["notes_dir"]
        path, fm, issues = add_link(d, "note-mt01", main_topic="FI0002")
        assert fm.main_topic == "FI0002"
        assert issues == []


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestLinkMainTopicCLI:
    def _seed(self, session, notes_dir):
        da = DisciplineArea(
            code="CL0002", name="CLI", discipline_num=2, topic_num=1, area_initials="CL"
        )
        session.add(da)
        session.flush()
        mt = MainTopic(code="CL0002", name="CLI Topic", discipline_area_id=da.id)
        session.add(mt)
        session.flush()
        note_row = Note(
            filename="cli-mt-01.md", reference="cli-mt-01", zettel_id="cli-mt-01"
        )
        session.add(note_row)
        session.commit()
        _write_note(notes_dir, "cli-mt-01", "CLI MainTopic Note")
        return {"note": note_row, "main_topic": mt}

    def test_cli_link_main_topic_exits_zero(self, runner, tmp_path):
        eng = _make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)
        result = runner.invoke(
            notes,
            ["link", "cli-mt-01", "--main-topic", "CL0002", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    def test_cli_link_main_topic_sets_frontmatter(self, runner, tmp_path):
        eng = _make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)
        runner.invoke(
            notes,
            ["link", "cli-mt-01", "--main-topic", "CL0002", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        text = (notes_dir / "cli-mt-01.md").read_text()
        assert "CL0002" in text

    def test_cli_link_main_topic_writes_fk(self, runner, tmp_path):
        eng = _make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            seeded = self._seed(session, notes_dir)
            mt_id = seeded["main_topic"].id
        runner.invoke(
            notes,
            ["link", "cli-mt-01", "--main-topic", "CL0002", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        with Session(eng) as session:
            note_row = session.scalars(
                select(Note).where(Note.zettel_id == "cli-mt-01")
            ).one()
            assert note_row.main_topic_id == mt_id

    def test_cli_link_main_topic_remove_flag(self, runner, tmp_path):
        eng = _make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)
        # Add first
        runner.invoke(
            notes,
            ["link", "cli-mt-01", "--main-topic", "CL0002", "--dir", str(notes_dir)],
            obj={"engine": eng},
        )
        # Remove
        result = runner.invoke(
            notes,
            ["link", "cli-mt-01", "--main-topic", "CL0002", "--remove", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        with Session(eng) as session:
            note_row = session.scalars(
                select(Note).where(Note.zettel_id == "cli-mt-01")
            ).one()
        assert note_row.main_topic_id is None

    def test_cli_link_main_topic_lenient_miss_warns(self, runner, tmp_path):
        eng = _make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)
        result = runner.invoke(
            notes,
            ["link", "cli-mt-01", "--main-topic", "UNKNOWN", "--dir", str(notes_dir)],
            obj={"engine": eng},
        )
        assert result.exit_code == 0, result.output
        assert "UNKNOWN" in result.output

    def test_cli_link_main_topic_strict_exits_nonzero(self, runner, tmp_path):
        eng = _make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)
        result = runner.invoke(
            notes,
            [
                "link", "cli-mt-01", "--main-topic", "UNKNOWN",
                "--strict", "--dir", str(notes_dir),
            ],
            obj={"engine": eng},
        )
        assert result.exit_code != 0
