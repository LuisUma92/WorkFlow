"""Tests for ADR ITEP-0009 Phase C: candidate_project frontmatter field."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.academic import DisciplineArea
from workflow.validation.schemas import (
    CANDIDATE_PROJECT_RE,
    check_candidate_project_against_db,
    validate_note_frontmatter,
)


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            DisciplineArea(
                code="0010MC",
                name="Mecánica",
                dewey="",
                discipline_num=0,
                topic_num=10,
                area_initials="MC",
            )
        )
        s.commit()
        yield s


def _base_note(**extra) -> dict:
    data = {"id": "n-1", "title": "Sample"}
    data.update(extra)
    return data


def test_regex_accepts_canonical():
    assert CANDIDATE_PROJECT_RE.match("0010MC-26ST")


@pytest.mark.parametrize(
    "bad",
    [
        "0010mc-26ST",  # lowercase area
        "0010MC-26st",  # lowercase initials
        "0010MC26ST",   # missing dash
        "010MC-26ST",   # short DD
        "0010MCC-26ST",  # wrong area length
        "0010MC-2ST",    # short year
    ],
)
def test_regex_rejects_malformed(bad):
    assert CANDIDATE_PROJECT_RE.match(bad) is None


def test_validate_accepts_well_formed_candidate():
    obj, errors = validate_note_frontmatter(
        _base_note(candidate_project="0010MC-26ST")
    )
    assert errors == []
    assert obj is not None
    assert obj.candidate_project == "0010MC-26ST"


def test_validate_absent_field_passes():
    obj, errors = validate_note_frontmatter(_base_note())
    assert errors == []
    assert obj is not None
    assert obj.candidate_project is None


def test_validate_rejects_malformed_value():
    obj, errors = validate_note_frontmatter(
        _base_note(candidate_project="bad-value")
    )
    assert obj is None
    assert any("candidate_project" in e for e in errors)


def test_validate_rejects_non_string():
    obj, errors = validate_note_frontmatter(_base_note(candidate_project=42))
    assert obj is None
    assert any("must be a string" in e for e in errors)


def test_warning_unknown_ddttaa(session):
    warnings = check_candidate_project_against_db("9999ZZ-26ST", session)
    assert len(warnings) == 1
    assert "9999ZZ" in warnings[0]


def test_no_warning_known_ddttaa(session):
    assert check_candidate_project_against_db("0010MC-26ST", session) == []


def test_warning_skipped_when_field_absent(session):
    assert check_candidate_project_against_db(None, session) == []
    assert check_candidate_project_against_db("", session) == []


def test_warning_skipped_when_field_malformed(session):
    # Caller already issued an error; helper does not double-fault.
    assert check_candidate_project_against_db("oops", session) == []
