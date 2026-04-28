"""Tests for ITEP-0008 changes to GeneralProject + MainTopic."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from workflow.db.engine import get_global_engine, get_global_session, init_global_db
from workflow.db.models.academic import DisciplineArea, MainTopic
from workflow.db.models.project import GeneralProject


@pytest.fixture
def session(tmp_path: Path):
    engine = get_global_engine(db_path=tmp_path / "wf.db")
    init_global_db(engine)
    sess = get_global_session(engine)
    yield sess
    sess.close()


@pytest.fixture
def area(session) -> MainTopic:
    a = MainTopic(name="Nuclear Physics", code="0060NP", parent_id=None)
    session.add(a)
    session.commit()
    return a


@pytest.fixture
def child(session, area) -> MainTopic:
    c = MainTopic(
        name="Scintillating Fibers",
        code="0060NP25SF",
        parent_id=area.id,
    )
    session.add(c)
    session.commit()
    return c


def _project(child_topic: MainTopic, **overrides) -> GeneralProject:
    base = dict(
        main_topic_id=child_topic.id,
        abs_parent_dir="/tmp/parent",
        abs_src_dir="/tmp/src",
        year_init=25,
        project_initials="SF",
        title="ScintillatingFibers",
    )
    base.update(overrides)
    return GeneralProject(**base)


class TestMainTopicHierarchy:
    def test_parent_id_links_children_to_area(self, session, area, child):
        assert child.parent is area
        assert child in area.children

    def test_area_has_no_parent(self, session, area):
        assert area.parent is None
        assert area.parent_id is None


class TestGeneralProjectFields:
    def test_root_dir_uses_area_yy_pp_title(self, session, area, child):
        gp = _project(child)
        session.add(gp)
        session.commit()
        assert gp.root_dir == "0060NP-25SF-ScintillatingFibers"

    def test_root_dir_legacy_fallback_when_unfilled(self, session, area, child):
        gp = _project(child, year_init=0, project_initials="", title="")
        session.add(gp)
        session.commit()
        # Pre-ITEP-0008 fallback: format reverts to "{code}-{name}".
        assert gp.root_dir == "0060NP25SF-Scintillating Fibers"

    def test_area_property_returns_parent(self, session, area, child):
        gp = _project(child)
        session.add(gp)
        session.commit()
        assert gp.area is area

    def test_status_defaults_to_active(self, session, area, child):
        gp = _project(child)
        session.add(gp)
        session.commit()
        assert gp.status == "active"
        assert gp.archived_at is None

    def test_status_check_constraint_rejects_unknown(self, session, area, child):
        gp = _project(child, status="bogus")
        session.add(gp)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_year_init_check_constraint_rejects_out_of_range(
        self, session, area, child
    ):
        gp = _project(child, year_init=100)
        session.add(gp)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_archive_records_date(self, session, area, child):
        gp = _project(child)
        session.add(gp)
        session.commit()
        gp.status = "archived"
        gp.archived_at = date(2026, 4, 21)
        session.commit()
        assert gp.status == "archived"
        assert gp.archived_at == date(2026, 4, 21)


class TestGeneralProjectUniqueness:
    def test_unique_main_topic_id(self, session, area, child):
        session.add(_project(child))
        session.commit()
        # Same child MainTopic → must collide on main_topic_id unique=True.
        session.add(_project(child, abs_parent_dir="/other"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_distinct_children_share_yy_pp_at_db_level(self, session, area):
        """(area, year_init, project_initials) uniqueness is enforced at the
        application layer (inittex), not in the DB. Two projects under the
        same area can collide on (yy, pp) without IntegrityError; the CLI is
        responsible for prior-check."""
        child_a = MainTopic(name="A", code="0060NP25SF", parent_id=area.id)
        child_b = MainTopic(name="B", code="0060NP25SX", parent_id=area.id)
        session.add_all([child_a, child_b])
        session.commit()
        session.add(_project(child_a))
        session.commit()
        session.add(_project(child_b))  # same yy=25, pp=SF — DB allows it.
        session.commit()
        assert session.query(GeneralProject).count() == 2


class TestDisciplineArea:
    def test_create_and_unique_code(self, session):
        da = DisciplineArea(
            code="0060NP",
            name="Nuclear Physics",
            dewey="539.7",
            discipline_num=0,
            topic_num=60,
            area_initials="NP",
        )
        session.add(da)
        session.commit()
        assert session.query(DisciplineArea).filter_by(code="0060NP").one() is da

        dup = DisciplineArea(
            code="0060NP",
            name="duplicate",
            discipline_num=0,
            topic_num=60,
            area_initials="NP",
        )
        session.add(dup)
        with pytest.raises(IntegrityError):
            session.commit()
