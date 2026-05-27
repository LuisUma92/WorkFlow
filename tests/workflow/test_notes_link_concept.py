"""ITEP-0012 P1 — notes link --concept materializes NoteConcept row.

Tests for:
- upsert_note_concept / delete_note_concept helpers
- add_link() with session + concept kwarg (lenient + strict + remove)
- CLI integration: --concept --remove --strict flags
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.knowledge import Concept
from workflow.db.models.notes import Note, NoteConcept
from workflow.notes.cli import notes
from workflow.notes.service import NoteNotFound, NoteValidationError, add_link


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_note(directory: Path, note_id: str, title: str = "Test", **kwargs) -> Path:
    fm = {
        "id": note_id,
        "title": title,
        "type": kwargs.get("type", "permanent"),
        "tags": list(kwargs.get("tags", [])),
        "concepts": list(kwargs.get("concepts", [])),
        "references": list(kwargs.get("references", [])),
        "exercises": list(kwargs.get("exercises", [])),
        "images": [],
    }
    body = kwargs.get("body", "## Body\n\nContent.\n")
    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n" + body
    path = directory / f"{note_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    """In-memory GlobalBase engine with all tables (includes Concept, NoteConcept)."""
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.project  # noqa: F401
    import workflow.db.models.notes  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401

    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


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
    """Seed one Note row + one Concept row; write the .md file."""
    da = DisciplineArea(code="FI0001", name="Fisica", discipline_num=1, topic_num=1, area_initials="FI")
    session.add(da)
    session.flush()

    mt = MainTopic(code="FI0001", name="Mecanica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()

    concept = Concept(code="forces", label="Forces", main_topic_id=mt.id)
    session.add(concept)
    session.flush()

    note_row = Note(filename="note-lc01.md", reference="note-lc01", zettel_id="note-lc01")
    session.add(note_row)
    session.commit()

    _write_note(notes_dir, "note-lc01", "Link Concept Test")

    return {"note": note_row, "concept": concept, "notes_dir": notes_dir}


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# unit: upsert_note_concept / delete_note_concept
# ---------------------------------------------------------------------------


class TestUpsertNoteConcept:
    def test_insert_returns_true(self, session, seeded):
        from workflow.notes.linker_ops import upsert_note_concept
        note_id = seeded["note"].id
        concept_id = seeded["concept"].id
        result = upsert_note_concept(session, note_id=note_id, concept_id=concept_id)
        assert result is True

    def test_second_call_returns_false(self, session, seeded):
        from workflow.notes.linker_ops import upsert_note_concept
        note_id = seeded["note"].id
        concept_id = seeded["concept"].id
        upsert_note_concept(session, note_id=note_id, concept_id=concept_id)
        result = upsert_note_concept(session, note_id=note_id, concept_id=concept_id)
        assert result is False

    def test_row_exists_in_db(self, session, seeded):
        from workflow.notes.linker_ops import upsert_note_concept
        note_id = seeded["note"].id
        concept_id = seeded["concept"].id
        upsert_note_concept(session, note_id=note_id, concept_id=concept_id)
        session.flush()
        rows = session.scalars(
            select(NoteConcept).where(
                NoteConcept.note_id == note_id,
                NoteConcept.concept_id == concept_id,
            )
        ).all()
        assert len(rows) == 1

    def test_delete_removes_row(self, session, seeded):
        from workflow.notes.linker_ops import delete_note_concept, upsert_note_concept
        note_id = seeded["note"].id
        concept_id = seeded["concept"].id
        upsert_note_concept(session, note_id=note_id, concept_id=concept_id)
        session.flush()
        deleted = delete_note_concept(session, note_id=note_id, concept_id=concept_id)
        assert deleted is True
        session.flush()
        rows = session.scalars(
            select(NoteConcept).where(
                NoteConcept.note_id == note_id,
                NoteConcept.concept_id == concept_id,
            )
        ).all()
        assert rows == []

    def test_delete_missing_returns_false(self, session, seeded):
        from workflow.notes.linker_ops import delete_note_concept
        result = delete_note_concept(
            session, note_id=seeded["note"].id, concept_id=seeded["concept"].id
        )
        assert result is False


# ---------------------------------------------------------------------------
# service: add_link with session
# ---------------------------------------------------------------------------


class TestAddLinkWithSession:
    def test_link_concept_creates_note_concept_row(self, session, seeded):
        d = seeded["notes_dir"]
        path, fm, issues = add_link(d, "note-lc01", concept="forces", session=session)
        session.flush()
        assert issues == []
        assert "forces" in fm.concepts
        rows = session.scalars(
            select(NoteConcept).where(NoteConcept.note_id == seeded["note"].id)
        ).all()
        assert len(rows) == 1
        assert rows[0].concept_id == seeded["concept"].id

    def test_link_concept_idempotent(self, session, seeded):
        d = seeded["notes_dir"]
        add_link(d, "note-lc01", concept="forces", session=session)
        session.flush()
        add_link(d, "note-lc01", concept="forces", session=session)
        session.flush()
        rows = session.scalars(
            select(NoteConcept).where(NoteConcept.note_id == seeded["note"].id)
        ).all()
        assert len(rows) == 1

    def test_link_concept_lenient_miss_skips_write(self, session, seeded):
        d = seeded["notes_dir"]
        original = (d / "note-lc01.md").read_text()
        path, fm, issues = add_link(d, "note-lc01", concept="unknown-code", session=session)
        # Frontmatter not modified
        assert "unknown-code" not in fm.concepts
        assert (d / "note-lc01.md").read_text() == original
        # No DB row
        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []
        # Warning in issues
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"

    def test_link_concept_strict_miss_raises(self, session, seeded):
        d = seeded["notes_dir"]
        with pytest.raises(NoteValidationError):
            add_link(d, "note-lc01", concept="unknown-code", session=session, strict=True)
        # No DB row
        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []

    def test_link_concept_remove_drops_row_and_fm_entry(self, session, seeded):
        d = seeded["notes_dir"]
        # First add it
        add_link(d, "note-lc01", concept="forces", session=session)
        session.flush()
        # Then remove it
        path, fm, issues = add_link(d, "note-lc01", concept="forces", session=session, remove=True)
        session.flush()
        assert "forces" not in fm.concepts
        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []

    def test_link_concept_remove_idempotent(self, session, seeded):
        d = seeded["notes_dir"]
        # Remove without prior link — should not error
        path, fm, issues = add_link(d, "note-lc01", concept="forces", session=session, remove=True)
        session.flush()
        # Call again — still clean
        path2, fm2, issues2 = add_link(d, "note-lc01", concept="forces", session=session, remove=True)
        session.flush()
        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []

    def test_link_concept_requires_synced_note(self, session, seeded):
        """Note on disk but zettel_id not in DB → NoteNotFound."""
        d = seeded["notes_dir"]
        _write_note(d, "unsynced-999", "Unsynced")
        with pytest.raises(NoteNotFound):
            add_link(d, "unsynced-999", concept="forces", session=session)

    def test_link_without_session_still_works(self, seeded):
        """Back-compat: no session → frontmatter-only path, 3-tuple returned."""
        d = seeded["notes_dir"]
        path, fm, issues = add_link(d, "note-lc01", concept="forces")
        assert "forces" in fm.concepts
        assert issues == []


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestLinkCmdCLI:
    def _make_engine(self):
        import workflow.db.models.bibliography  # noqa: F401
        import workflow.db.models.academic  # noqa: F401
        import workflow.db.models.project  # noqa: F401
        import workflow.db.models.notes  # noqa: F401
        import workflow.db.models.exercises  # noqa: F401

        eng = create_engine("sqlite:///:memory:")
        event.listen(eng, "connect", _enable_fk)
        GlobalBase.metadata.create_all(eng)
        return eng

    def _seed(self, session, notes_dir):
        da = DisciplineArea(code="CL0001", name="CLI", discipline_num=1, topic_num=1, area_initials="CL")
        session.add(da)
        session.flush()
        mt = MainTopic(code="CL0001", name="CLI Topic", discipline_area_id=da.id)
        session.add(mt)
        session.flush()
        concept = Concept(code="cli-force", label="CLI Force", main_topic_id=mt.id)
        session.add(concept)
        session.flush()
        note_row = Note(filename="cli-note-01.md", reference="cli-note-01", zettel_id="cli-note-01")
        session.add(note_row)
        session.commit()
        _write_note(notes_dir, "cli-note-01", "CLI Note")
        return {"note": note_row, "concept": concept}

    def test_cli_link_concept_exits_zero(self, runner, tmp_path):
        eng = self._make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)

        result = runner.invoke(
            notes,
            ["link", "cli-note-01", "--concept", "cli-force", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    def test_cli_link_concept_creates_db_row(self, runner, tmp_path):
        eng = self._make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            seeded = self._seed(session, notes_dir)

        result = runner.invoke(
            notes,
            ["link", "cli-note-01", "--concept", "cli-force", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        with Session(eng) as session:
            rows = session.scalars(select(NoteConcept)).all()
        assert len(rows) == 1

    def test_cli_link_concept_remove_flag(self, runner, tmp_path):
        eng = self._make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)

        # Add first
        runner.invoke(
            notes,
            ["link", "cli-note-01", "--concept", "cli-force", "--dir", str(notes_dir)],
            obj={"engine": eng},
        )
        # Then remove
        result = runner.invoke(
            notes,
            ["link", "cli-note-01", "--concept", "cli-force", "--remove", "--dir", str(notes_dir)],
            obj={"engine": eng},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        with Session(eng) as session:
            rows = session.scalars(select(NoteConcept)).all()
        assert rows == []

    def test_cli_link_lenient_miss_warns_to_stderr(self, runner, tmp_path):
        eng = self._make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)

        result = runner.invoke(
            notes,
            ["link", "cli-note-01", "--concept", "nonexistent", "--dir", str(notes_dir)],
            obj={"engine": eng},
        )
        # Exit 0 (lenient)
        assert result.exit_code == 0, result.output
        # Warning message appears in combined output (Click mixes stderr into output by default)
        assert "nonexistent" in result.output

    def test_cli_link_strict_miss_exits_nonzero(self, runner, tmp_path):
        eng = self._make_engine()
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        with Session(eng) as session:
            self._seed(session, notes_dir)

        result = runner.invoke(
            notes,
            ["link", "cli-note-01", "--concept", "nonexistent", "--strict", "--dir", str(notes_dir)],
            obj={"engine": eng},
        )
        assert result.exit_code != 0
