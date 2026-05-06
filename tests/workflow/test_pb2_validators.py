"""Phase B.2 — main_topic + discipline_area validators."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
import workflow.db.models.academic  # noqa: F401
import workflow.db.models.notes  # noqa: F401
from workflow.db.models.academic import DisciplineArea, MainTopic
from workflow.validation.schemas import (
    check_discipline_area_consistency,
    check_main_topic_against_db,
)


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def _seed(session, area_code: str = "FI0006", topic_code: str = "FI0006"):
    da = DisciplineArea(
        code=area_code, name="Mecánica",
        discipline_num=1, topic_num=6, area_initials="FI",
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code=topic_code, name="Mecánica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    return da, mt


# ── check_main_topic_against_db ────────────────────────────────────────────


def test_main_topic_none_returns_empty(session):
    obj, msgs = check_main_topic_against_db(None, session)
    assert obj is None
    assert msgs == []


def test_main_topic_known_slug_resolves(session):
    _, mt = _seed(session)
    obj, msgs = check_main_topic_against_db("FI0006", session)
    assert obj is not None
    assert obj.id == mt.id
    assert msgs == []


def test_main_topic_known_int_id_resolves(session):
    _, mt = _seed(session)
    obj, msgs = check_main_topic_against_db(mt.id, session)
    assert obj is not None
    assert obj.id == mt.id
    assert msgs == []


def test_main_topic_int_str_resolves_as_id_first(session):
    """A numeric string like '1' tries id lookup first."""
    _, mt = _seed(session)
    obj, msgs = check_main_topic_against_db(str(mt.id), session)
    assert obj is not None
    assert obj.id == mt.id


def test_main_topic_unknown_slug_warns(session):
    _seed(session)
    obj, msgs = check_main_topic_against_db("FI9999", session)
    assert obj is None
    assert len(msgs) == 1
    assert "FI9999" in msgs[0]


def test_main_topic_unknown_id_warns(session):
    _seed(session)
    obj, msgs = check_main_topic_against_db(99999, session)
    assert obj is None
    assert len(msgs) == 1


# ── check_discipline_area_consistency ──────────────────────────────────────


def test_discipline_area_consistency_match(session):
    da, mt = _seed(session)
    msgs = check_discipline_area_consistency(mt, "FI0006", session)
    assert msgs == []


def test_discipline_area_consistency_mismatch(session):
    da, mt = _seed(session, area_code="FI0006", topic_code="FI0006")
    other = DisciplineArea(
        code="MA0250", name="Cálculo",
        discipline_num=2, topic_num=50, area_initials="MA",
    )
    session.add(other)
    session.flush()

    msgs = check_discipline_area_consistency(mt, "MA0250", session)
    assert len(msgs) == 1
    assert "inconsistency" in msgs[0]


def test_discipline_area_unknown_in_ref_table(session):
    _, mt = _seed(session)
    msgs = check_discipline_area_consistency(mt, "ZZ9999", session)
    assert len(msgs) == 1
    assert "not found" in msgs[0]


def test_discipline_area_consistency_skips_when_main_topic_missing(session):
    msgs = check_discipline_area_consistency(None, "FI0006", session)
    assert msgs == []


def test_discipline_area_consistency_skips_when_da_missing(session):
    _, mt = _seed(session)
    msgs = check_discipline_area_consistency(mt, None, session)
    assert msgs == []
