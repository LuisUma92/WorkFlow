"""ITEP-0012 P2 — sync_vault materializes NoteConcept rows from frontmatter concepts:.

Tests for _sync_note_concepts pass inside sync_vault:
- Creates rows from concepts: list
- Idempotent (double sync keeps count stable)
- Lenient: unknown code → warning, no row
- Strict: unknown code → error in report, sys.exit(1) from CLI
- Empty concepts list → noop
- SyncReport.concept_links_created counter
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic, Topic, Content
from workflow.db.models.knowledge import Concept
from workflow.db.models.notes import Note, NoteConcept
from workflow.notes.cli import notes
from workflow.notes.sync import sync_vault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_note(directory: Path, note_id: str, concepts: list[str] | None = None) -> Path:
    fm = {
        "id": note_id,
        "title": f"Note {note_id}",
        "type": "permanent",
        "tags": [],
        "concepts": concepts or [],
        "references": [],
        "exercises": [],
        "images": [],
    }
    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n\nBody.\n"
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
def vault(tmp_path):
    d = tmp_path / "vault"
    d.mkdir()
    return d


@pytest.fixture()
def seeded(session, vault):
    """Seed two Concept rows, no Note rows (sync_vault will create them)."""
    da = DisciplineArea(code="SC0001", name="Science", discipline_num=1, topic_num=1, area_initials="SC")
    session.add(da)
    session.flush()

    mt = MainTopic(code="SC0001", name="Physics", discipline_area_id=da.id)
    session.add(mt)
    session.flush()

    tp = Topic(discipline_area_id=da.id, name="Mechanics", serial_number=1)
    session.add(tp)
    session.flush()

    ct = Content(topic_id=tp.id, name="Classical Mechanics")
    session.add(ct)
    session.flush()

    c1 = Concept(code="gravity", label="Gravity", content_id=ct.id, domain="Información")
    c2 = Concept(code="momentum", label="Momentum", content_id=ct.id, domain="Información")
    session.add(c1)
    session.add(c2)
    session.commit()

    return {"da": da, "mt": mt, "tp": tp, "ct": ct, "c1": c1, "c2": c2, "vault": vault}


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncCreatesNoteConcept:
    def test_sync_creates_note_concept_rows(self, session, seeded):
        vault = seeded["vault"]
        _write_note(vault, "note-sc01", concepts=["gravity"])
        _write_note(vault, "note-sc02", concepts=["momentum"])

        report = sync_vault(vault, session)
        session.commit()

        rows = session.scalars(select(NoteConcept)).all()
        assert len(rows) == 2

    def test_sync_concept_idempotent(self, session, seeded):
        vault = seeded["vault"]
        _write_note(vault, "note-idem01", concepts=["gravity"])

        sync_vault(vault, session)
        session.commit()
        count_after_first = session.query(NoteConcept).count()

        sync_vault(vault, session)
        session.commit()
        count_after_second = session.query(NoteConcept).count()

        assert count_after_first == count_after_second == 1

    def test_sync_lenient_unknown_code_warns_no_row(self, session, seeded):
        vault = seeded["vault"]
        _write_note(vault, "note-lenient01", concepts=["nonexistent-code"])

        report = sync_vault(vault, session)
        session.commit()

        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []
        assert len(report.concept_issues) == 1
        assert report.concept_issues[0]["severity"] == "warning"
        assert "nonexistent-code" in report.concept_issues[0]["message"]

    def test_sync_strict_unknown_code_records_error(self, session, seeded):
        vault = seeded["vault"]
        _write_note(vault, "note-strict01", concepts=["bad-code"])

        report = sync_vault(vault, session, strict_concepts=True)

        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []
        assert len(report.concept_issues) == 1
        assert report.concept_issues[0]["severity"] == "error"

    def test_sync_empty_concepts_list_noop(self, session, seeded):
        vault = seeded["vault"]
        _write_note(vault, "note-empty01", concepts=[])

        report = sync_vault(vault, session)
        session.commit()

        rows = session.scalars(select(NoteConcept)).all()
        assert rows == []
        assert report.concept_links_created == 0
        assert report.concept_issues == []

    def test_sync_report_counter(self, session, seeded):
        vault = seeded["vault"]
        _write_note(vault, "note-cnt01", concepts=["gravity"])
        _write_note(vault, "note-cnt02", concepts=["momentum"])
        _write_note(vault, "note-cnt03", concepts=["gravity", "momentum"])

        report = sync_vault(vault, session)
        session.commit()

        assert report.concept_links_created == 4


class TestSyncConceptCLI:
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

    def _seed(self, session):
        da = DisciplineArea(code="TC0001", name="Test", discipline_num=1, topic_num=1, area_initials="TC")
        session.add(da)
        session.flush()
        mt = MainTopic(code="TC0001", name="Test Topic", discipline_area_id=da.id)
        session.add(mt)
        session.flush()
        tp = Topic(discipline_area_id=da.id, name="Test Subtopic", serial_number=1)
        session.add(tp)
        session.flush()
        ct = Content(topic_id=tp.id, name="Test Content")
        session.add(ct)
        session.flush()
        c = Concept(code="test-concept", label="Test Concept", content_id=ct.id, domain="Información")
        session.add(c)
        session.commit()
        return c

    def test_sync_strict_concepts_exits_nonzero(self, runner, tmp_path):
        eng = self._make_engine()
        vault = tmp_path / "vault"
        vault.mkdir()
        with Session(eng) as session:
            self._seed(session)
        _write_note(vault, "note-cli01", concepts=["unknown-bad"])

        result = runner.invoke(
            notes,
            ["sync", "--strict-concepts"],
            obj={"engine": eng},
            env={"WORKFLOW_VAULT_ROOT": str(vault)},
        )
        # Should exit non-zero due to error-severity concept issues
        assert result.exit_code != 0

    def test_sync_json_includes_concept_links_created(self, runner, tmp_path):
        eng = self._make_engine()
        vault = tmp_path / "vault"
        vault.mkdir()
        with Session(eng) as session:
            self._seed(session)
        _write_note(vault, "note-json01", concepts=["test-concept"])

        result = runner.invoke(
            notes,
            ["sync", "--json"],
            obj={"engine": eng},
            env={"WORKFLOW_VAULT_ROOT": str(vault)},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "concept_links_created" in data
        assert data["concept_links_created"] == 1
