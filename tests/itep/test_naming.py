"""Tests for itep.naming (ADR ITEP-0008 Phase C)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.project import GeneralProject
from itep import naming


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def _seed_area(
    session: Session, code: str = "0110EP", name: str = "Lógica"
) -> MainTopic:
    da = DisciplineArea(
        code=code,
        name=name,
        discipline_num=int(code[:2]),
        topic_num=int(code[2:4]),
        area_initials=code[4:6],
    )
    session.add(da)
    session.flush()
    area = MainTopic(
        name=name,
        code=code,
        parent_id=None,
        discipline_area_id=da.id,
    )
    session.add(area)
    session.commit()
    return area


def _seed_project(
    session: Session, area: MainTopic, yy: int, pp: str, title: str
) -> GeneralProject:
    child = MainTopic(
        name=title,
        code=f"{area.code}{yy:02d}{pp}",
        parent_id=area.id,
        discipline_area_id=area.discipline_area_id,
    )
    session.add(child)
    session.flush()
    proj = GeneralProject(
        main_topic_id=child.id,
        abs_parent_dir="/tmp",
        abs_src_dir="/tmp",
        year_init=yy,
        project_initials=pp,
        title=title,
    )
    session.add(proj)
    session.commit()
    return proj


# ── candidates / slugify ───────────────────────────────────────────────


def test_candidates_two_words():
    out = naming.candidates("Sample Theory")
    assert out[0].value == "ST"
    assert out[1].value == "SA"
    assert out[2].value == "TH"


def test_candidates_one_word_only():
    out = naming.candidates("Theory")
    assert out[0].value == ""
    assert out[1].value == "TH"
    assert out[2].value == ""


def test_candidates_strip_accents_and_punct():
    out = naming.candidates("Mecánica-Clásica!")
    assert out[0].value == "MC"
    assert out[1].value == "ME"
    assert out[2].value == "CL"


def test_slugify_title_camelcase():
    assert naming.slugify_title("Sample Theory") == "SampleTheory"
    assert naming.slugify_title("Mecánica Clásica") == "MecanicaClasica"
    assert naming.slugify_title("one") == "One"


def test_validate_pp_ok():
    assert naming.validate_pp("sf") == "SF"


def test_validate_pp_rejects_digits():
    with pytest.raises(ValueError):
        naming.validate_pp("S1")


def test_validate_pp_rejects_length():
    with pytest.raises(ValueError):
        naming.validate_pp("ABC")


# ── derive_project_initials ────────────────────────────────────────────


def test_derive_first_rule_wins(session):
    area = _seed_area(session)
    cand = naming.derive_project_initials("Sample Theory", session, area.id, 26)
    assert cand is not None
    assert cand.rule == "word_initials"
    assert cand.value == "ST"


def test_derive_falls_through_on_collision(session):
    area = _seed_area(session)
    _seed_project(session, area, yy=26, pp="ST", title="Sample Theory")
    cand = naming.derive_project_initials("Sample Thinking", session, area.id, 26)
    # ST taken → fallback to word1_prefix "SA"
    assert cand is not None
    assert cand.rule == "word1_prefix"
    assert cand.value == "SA"


def test_derive_returns_none_when_all_taken(session):
    area = _seed_area(session)
    _seed_project(session, area, 26, "ST", "Sample Theory")
    _seed_project(session, area, 26, "SA", "Sample A")
    _seed_project(session, area, 26, "TH", "T H")
    cand = naming.derive_project_initials("Sample Theory", session, area.id, 26)
    assert cand is None


def test_derive_extra_taken_blocks_match(session):
    area = _seed_area(session)
    cand = naming.derive_project_initials(
        "Sample Theory", session, area.id, 26, extra_taken={"ST"}
    )
    assert cand is not None
    assert cand.value == "SA"


def test_is_taken_respects_area_isolation(session):
    area1 = _seed_area(session, code="0110EP", name="Logic")
    area2 = _seed_area(session, code="0210CS", name="CS")
    _seed_project(session, area1, 26, "ST", "Sample")
    assert naming.is_taken(session, area1.id, 26, "ST") is True
    assert naming.is_taken(session, area2.id, 26, "ST") is False
