"""Phase B — NoteFrontmatter schema + check_main_topic_against_db validator.

Tests:
- optional main_topic / discipline_area fields (schema level)
- check_main_topic_against_db: slug, id, missing, strict vs lenient
- check_discipline_area_consistency: mismatch, missing, consistent
- validate notes --strict-main-topic CLI flag integration
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import workflow.db.models.academic  # noqa: F401
import workflow.db.models.bibliography  # noqa: F401
import workflow.db.models.exercises  # noqa: F401
import workflow.db.models.notes  # noqa: F401
import workflow.db.models.project  # noqa: F401
from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.validation.cli import validate
from workflow.validation.schemas import (
    check_discipline_area_consistency,
    check_main_topic_against_db,
    validate_note_frontmatter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def seeded_mt(session):
    """Seed DisciplineArea + MainTopic."""
    da = DisciplineArea(
        code="FI0001", name="Fisica", discipline_num=1, topic_num=1, area_initials="FI"
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code="FI0001", name="Mecanica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    return da, mt


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Schema: optional fields forward-compatibility
# ---------------------------------------------------------------------------


class TestNoteFrontmatterSchema:
    def _base(self, **kw) -> dict:
        return {"id": "n-1", "title": "Test Note", **kw}

    def test_without_main_topic_validates(self):
        fm, errs = validate_note_frontmatter(self._base())
        assert errs == []
        assert fm is not None
        assert fm.main_topic is None
        assert fm.discipline_area is None

    def test_with_main_topic_slug_validates(self):
        fm, errs = validate_note_frontmatter(self._base(main_topic="FI0001"))
        assert errs == []
        assert fm is not None
        assert fm.main_topic == "FI0001"

    def test_with_main_topic_int_validates(self):
        fm, errs = validate_note_frontmatter(self._base(main_topic=42))
        assert errs == []
        assert fm is not None
        assert fm.main_topic == 42

    def test_main_topic_bool_rejected(self):
        fm, errs = validate_note_frontmatter(self._base(main_topic=True))
        assert fm is None
        assert any("main_topic" in e for e in errs)

    def test_main_topic_list_rejected(self):
        fm, errs = validate_note_frontmatter(self._base(main_topic=["a"]))
        assert fm is None
        assert any("main_topic" in e for e in errs)

    def test_with_discipline_area_validates(self):
        fm, errs = validate_note_frontmatter(self._base(discipline_area="FI0001"))
        assert errs == []
        assert fm is not None
        assert fm.discipline_area == "FI0001"

    def test_discipline_area_bad_format_rejected(self):
        fm, errs = validate_note_frontmatter(self._base(discipline_area="bad"))
        assert fm is None
        assert any("discipline_area" in e for e in errs)

    def test_discipline_area_non_string_rejected(self):
        fm, errs = validate_note_frontmatter(self._base(discipline_area=123))
        assert fm is None
        assert any("discipline_area" in e for e in errs)

    def test_both_fields_absent_no_error(self):
        """Legacy notes without main_topic/discipline_area validate cleanly."""
        fm, errs = validate_note_frontmatter(
            {"id": "legacy-01", "title": "Old Note", "tags": ["physics"]}
        )
        assert errs == []
        assert fm is not None


# ---------------------------------------------------------------------------
# check_main_topic_against_db
# ---------------------------------------------------------------------------


class TestCheckMainTopicAgainstDb:
    def test_none_returns_none_no_messages(self, session, seeded_mt):
        mt_obj, msgs = check_main_topic_against_db(None, session)
        assert mt_obj is None
        assert msgs == []

    def test_resolves_by_slug(self, session, seeded_mt):
        _, mt = seeded_mt
        mt_obj, msgs = check_main_topic_against_db("FI0001", session)
        assert mt_obj is not None
        assert mt_obj.code == "FI0001"
        assert msgs == []

    def test_resolves_by_int_id(self, session, seeded_mt):
        _, mt = seeded_mt
        mt_obj, msgs = check_main_topic_against_db(mt.id, session)
        assert mt_obj is not None
        assert mt_obj.id == mt.id
        assert msgs == []

    def test_resolves_int_string(self, session, seeded_mt):
        _, mt = seeded_mt
        mt_obj, msgs = check_main_topic_against_db(str(mt.id), session)
        assert mt_obj is not None
        assert mt_obj.id == mt.id

    def test_unknown_slug_lenient_returns_message(self, session, seeded_mt):
        mt_obj, msgs = check_main_topic_against_db("UNKNOWN", session, strict=False)
        assert mt_obj is None
        assert len(msgs) == 1
        assert "UNKNOWN" in msgs[0]

    def test_unknown_slug_strict_same_message(self, session, seeded_mt):
        """strict= flag doesn't change the message; caller routes it."""
        mt_obj, msgs = check_main_topic_against_db("UNKNOWN", session, strict=True)
        assert mt_obj is None
        assert len(msgs) == 1


# ---------------------------------------------------------------------------
# check_discipline_area_consistency
# ---------------------------------------------------------------------------


class TestCheckDisciplineAreaConsistency:
    def test_both_none_returns_empty(self, session, seeded_mt):
        result = check_discipline_area_consistency(None, None, session)
        assert result == []

    def test_mt_none_returns_empty(self, session, seeded_mt):
        result = check_discipline_area_consistency(None, "FI0001", session)
        assert result == []

    def test_da_none_returns_empty(self, session, seeded_mt):
        _, mt = seeded_mt
        result = check_discipline_area_consistency(mt, None, session)
        assert result == []

    def test_consistent_returns_empty(self, session, seeded_mt):
        da, mt = seeded_mt
        result = check_discipline_area_consistency(mt, da.code, session)
        assert result == []

    def test_unknown_da_code_returns_error(self, session, seeded_mt):
        _, mt = seeded_mt
        result = check_discipline_area_consistency(mt, "XX9999", session)
        assert len(result) == 1
        assert "XX9999" in result[0]

    def test_mismatched_da_returns_error(self, session, seeded_mt):
        da, mt = seeded_mt
        # Seed a second discipline area
        da2 = DisciplineArea(
            code="BI0001", name="Bio", discipline_num=2, topic_num=1, area_initials="BI"
        )
        session.add(da2)
        session.flush()
        result = check_discipline_area_consistency(mt, "BI0001", session)
        assert len(result) == 1
        assert "BI0001" in result[0] or "FI0001" in result[0]


# ---------------------------------------------------------------------------
# CLI: workflow validate notes --strict-main-topic
# ---------------------------------------------------------------------------


class TestValidateNotesCliStrictMainTopic:
    def _write_note(self, path: Path, note_id: str, **fm_extra) -> None:
        fm = {
            "id": note_id,
            "title": "Test",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
            **fm_extra,
        }
        content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n"
        (path / f"{note_id}.md").write_text(content, encoding="utf-8")

    def test_no_main_topic_exits_zero(self, runner, tmp_path, engine):
        self._write_note(tmp_path, "note-nmt")
        result = runner.invoke(
            validate,
            ["notes", str(tmp_path), "--no-recursive"],
            obj={"engine": engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    def test_known_main_topic_exits_zero(self, runner, tmp_path, engine, seeded_mt):
        da, mt = seeded_mt
        # seeded_mt uses session already committed?
        # Re-seed via engine
        with Session(engine) as s:
            da2 = DisciplineArea(
                code="VM0001", name="Vascular", discipline_num=9, topic_num=1, area_initials="VM"
            )
            s.add(da2)
            s.flush()
            mt2 = MainTopic(code="VM0001", name="Vascular", discipline_area_id=da2.id)
            s.add(mt2)
            s.commit()
        self._write_note(tmp_path, "note-kmt", main_topic="VM0001")
        result = runner.invoke(
            validate,
            ["notes", str(tmp_path), "--no-recursive"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    def test_unknown_main_topic_lenient_exits_zero(self, runner, tmp_path):
        self._write_note(tmp_path, "note-unk", main_topic="UNKN01")
        result = runner.invoke(
            validate,
            ["notes", str(tmp_path), "--no-recursive"],
            catch_exceptions=False,
        )
        # lenient: warning but exit 0
        assert result.exit_code == 0, result.output

    def test_unknown_main_topic_strict_exits_nonzero(self, runner, tmp_path):
        self._write_note(tmp_path, "note-unk2", main_topic="UNKN02")
        result = runner.invoke(
            validate,
            ["notes", str(tmp_path), "--no-recursive", "--strict-main-topic"],
        )
        assert result.exit_code != 0
