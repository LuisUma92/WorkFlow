"""Tests for ADR ITEP-0009 Phase B: maturation primitives + CLI."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.cli import db  # noqa: F401  -- ensure registration
from workflow.db import maturation
from workflow.db.models.knowledge import Content, DisciplineArea, MainTopic, Topic
from workflow.db.models.bibliography import BibContent
from workflow.db.models.academic import (
    Course,
    CourseContent,
    Institution,
)
from workflow.db.models.bibliography import BibEntry
from workflow.db.models.project import LectureInstance
from workflow.db.engine import get_global_engine, init_global_db
from workflow.project.cli import project as project_cli


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def _ensure_discipline_area(session, code: str, name: str) -> DisciplineArea:
    existing = session.query(DisciplineArea).filter_by(code=code).first()
    if existing is not None:
        return existing
    da = DisciplineArea(
        code=code,
        name=name,
        discipline_num=int(code[:2]),
        topic_num=int(code[2:4]),
        area_initials=code[4:6],
    )
    session.add(da)
    session.commit()
    return da


def _make_area(session, code: str = "0010MC", name: str = "Mecánica") -> MainTopic:
    da = _ensure_discipline_area(session, code, name)
    a = MainTopic(code=code, name=name, parent_id=None, discipline_area_id=da.id)
    session.add(a)
    session.commit()
    return a


def _make_topic(session, area: MainTopic, name: str = "T") -> Topic:
    t = Topic(main_topic_id=area.id, name=name, serial_number=1)
    session.add(t)
    session.commit()
    return t


def _make_content(session, topic: Topic) -> Content:
    c = Content(
        topic_id=topic.id,
        name="Section",
    )
    session.add(c)
    session.commit()
    return c


def _attach_bib(session, content: Content, n: int) -> None:
    for i in range(n):
        bib = BibEntry(bibkey=f"k{content.id}_{i}", entry_type="article")
        session.add(bib)
        session.flush()
        session.add(BibContent(
            bib_entry_id=bib.id,
            content_id=content.id,
            chapter_number=1,
            section_number=1,
            first_page=1,
            last_page=10,
        ))
    session.commit()


def _attach_course(session, content: Content, code: str) -> Course:
    institution = session.query(Institution).filter_by(
        short_name="UCR"
    ).first() or Institution(
        short_name="UCR",
        full_name="UCR",
        cycle_weeks=18,
        cycle_name="Semestre",
    )
    if institution.id is None:
        session.add(institution)
        session.flush()
    course = Course(institution_id=institution.id, code=code, name=code)
    session.add(course)
    session.flush()
    session.add(
        CourseContent(course_id=course.id, content_id=content.id, lecture_week=1)
    )
    session.commit()
    return course


# ── evaluate_area ─────────────────────────────────────────────────────


def test_evaluate_area_rejects_non_area(session):
    area = _make_area(session)
    child = MainTopic(
        code="0010MC26ST",
        name="Child",
        parent_id=area.id,
        discipline_area_id=area.discipline_area_id,
    )
    session.add(child)
    session.commit()
    with pytest.raises(ValueError, match="not an area"):
        maturation.evaluate_area(session, child.id)


def test_evaluate_area_unknown_id(session):
    with pytest.raises(ValueError, match="not found"):
        maturation.evaluate_area(session, 9999)


def test_evaluate_area_all_negative_when_empty(session):
    area = _make_area(session)
    signals = maturation.evaluate_area(session, area.id)
    queryable = [s for s in signals if s.met is not None]
    assert all(s.met is False for s in queryable)
    assert maturation.is_mature(signals) is False
    assert maturation.all_queryable_negative(signals) is True


def test_bib_threshold_default_is_three(session):
    area = _make_area(session, code="0010MC")  # DD=00 → not hobby
    topic = _make_topic(session, area)
    content = _make_content(session, topic)
    _attach_bib(session, content, n=2)
    s = {x.criterion: x for x in maturation.evaluate_area(session, area.id)}
    assert s["bibliographic_accumulation"].met is False
    _attach_bib(session, content, n=1)  # total 3
    s = {x.criterion: x for x in maturation.evaluate_area(session, area.id)}
    assert s["bibliographic_accumulation"].met is True
    assert maturation.is_mature(maturation.evaluate_area(session, area.id))


def test_bib_threshold_hobby_is_five(session):
    area = _make_area(session, code="0410LG", name="Lingüística")  # DD=04
    topic = _make_topic(session, area)
    content = _make_content(session, topic)
    _attach_bib(session, content, n=4)
    s = {x.criterion: x for x in maturation.evaluate_area(session, area.id)}
    assert s["bibliographic_accumulation"].met is False
    assert "threshold=5" in s["bibliographic_accumulation"].evidence
    _attach_bib(session, content, n=1)  # total 5
    s = {x.criterion: x for x in maturation.evaluate_area(session, area.id)}
    assert s["bibliographic_accumulation"].met is True


def test_institutional_affiliation_signal(session):
    area = _make_area(session)
    topic = _make_topic(session, area)
    content = _make_content(session, topic)
    _attach_course(session, content, "FS0121")
    s = {x.criterion: x for x in maturation.evaluate_area(session, area.id)}
    assert s["institutional_affiliation"].met is True


def test_multi_semester_continuity_signal(session):
    from datetime import date as _d

    area = _make_area(session)
    topic = _make_topic(session, area)
    content = _make_content(session, topic)
    course = _attach_course(session, content, "FS0121")
    for cycle in (1, 2):
        session.add(
            LectureInstance(
                course_id=course.id,
                year=2026,
                cycle=cycle,
                first_monday=_d(2026, 3, 2),
                abs_parent_dir="/tmp",
                abs_src_dir="/tmp",
            )
        )
    session.commit()
    s = {x.criterion: x for x in maturation.evaluate_area(session, area.id)}
    assert s["multi_semester_continuity"].met is True


def test_children_topics_count_toward_bib(session):
    area = _make_area(session)
    child = MainTopic(
        code="0010MC26ST",
        name="Child",
        parent_id=area.id,
        discipline_area_id=area.discipline_area_id,
    )
    session.add(child)
    session.flush()
    topic = Topic(main_topic_id=child.id, name="Sub", serial_number=1)
    session.add(topic)
    session.flush()
    content = _make_content(session, topic)
    _attach_bib(session, content, n=3)
    signals = maturation.evaluate_area(session, area.id)
    s = {x.criterion: x for x in signals}
    assert s["bibliographic_accumulation"].met is True


def test_non_queryable_signals_remain_none(session):
    area = _make_area(session)
    signals = {s.criterion: s for s in maturation.evaluate_area(session, area.id)}
    assert signals["formal_product"].met is None
    assert signals["systematic_review"].met is None
    assert signals["collaborative_scope"].met is None


# ── workflow project propose-maturation CLI ───────────────────────────


@pytest.fixture()
def cli_runner_engine(tmp_path, monkeypatch):
    engine = get_global_engine(db_path=tmp_path / "wf.db")
    init_global_db(engine)

    def _fake(_ctx):
        return engine

    monkeypatch.setattr("workflow.project.cli.get_engine_from_ctx", _fake)
    return engine


def test_propose_maturation_empty_db(cli_runner_engine):
    runner = CliRunner()
    result = runner.invoke(project_cli, ["propose-maturation"])
    assert result.exit_code == 0, result.output
    assert "No area-level MainTopic" in result.output


def test_propose_maturation_table_and_json(cli_runner_engine):
    with Session(cli_runner_engine) as s:
        da = _ensure_discipline_area(s, "0010MC", "Mecánica")
        s.add(
            MainTopic(
                code="0010MC",
                name="Mecánica",
                parent_id=None,
                discipline_area_id=da.id,
            )
        )
        s.commit()
    runner = CliRunner()
    result = runner.invoke(project_cli, ["propose-maturation"])
    assert result.exit_code == 0, result.output
    assert "0010MC" in result.output
    assert "bibliographic_accumulation" in result.output

    result = runner.invoke(project_cli, ["propose-maturation", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert len(parsed) == 1
    assert parsed[0]["area_code"] == "0010MC"
    assert parsed[0]["mature"] is False


def test_propose_maturation_area_filter(cli_runner_engine):
    with Session(cli_runner_engine) as s:
        da_a = _ensure_discipline_area(s, "0010MC", "A")
        da_b = _ensure_discipline_area(s, "0110EP", "B")
        s.add(
            MainTopic(
                code="0010MC",
                name="A",
                parent_id=None,
                discipline_area_id=da_a.id,
            )
        )
        s.add(
            MainTopic(
                code="0110EP",
                name="B",
                parent_id=None,
                discipline_area_id=da_b.id,
            )
        )
        s.commit()
    runner = CliRunner()
    result = runner.invoke(
        project_cli, ["propose-maturation", "--area", "0010MC", "--json"]
    )
    parsed = json.loads(result.output)
    assert [e["area_code"] for e in parsed] == ["0010MC"]


# ── create_general warning ────────────────────────────────────────────


def test_create_general_blocks_when_no_maturation(tmp_path):
    """create_general aborts on `n` when area has zero queryable signals."""
    from itep.create import create_general
    from workflow.db.models.knowledge import DisciplineArea
    import click as _click

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

        parent = tmp_path / "parent"
        parent.mkdir()
        src = tmp_path / "src"
        src.mkdir()

        # Simulate user typing "n" via monkeypatching click.confirm.
        import workflow.db.maturation  # noqa: F401
        import itep.create as create_mod

        original = create_mod.click.confirm
        create_mod.click.confirm = lambda *_a, **_kw: False
        try:
            with pytest.raises(_click.Abort):
                create_general(
                    s,
                    parent,
                    src,
                    title="Foo Bar",
                    year_init=26,
                    area_code="0010MC",
                )
        finally:
            create_mod.click.confirm = original
