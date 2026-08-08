"""End-to-end tests for itep.create.create_general (ADR ITEP-0008 Phase C)."""

from __future__ import annotations

from datetime import date

import click
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from types import SimpleNamespace

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.db.models.project import GeneralProject
from itep.create import create_general, _create_dirs_from_tree
from itep.models import LectureProject


@pytest.fixture()
def session(tmp_path):
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            DisciplineArea(
                code="0110EP",
                name="Lógica",
                dewey="160",
                discipline_num=1,
                topic_num=10,
                area_initials="EP",
            )
        )
        s.commit()
        yield s


def test_create_general_creates_full_hierarchy(session, tmp_path):
    parent = tmp_path / "parent"
    src = tmp_path / "src"
    parent.mkdir()
    src.mkdir()

    proj = create_general(
        session,
        parent_dir=parent,
        src_dir=src,
        title="Sample Theory",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )

    assert proj.year_init == 26
    assert proj.project_initials == "ST"
    assert proj.title == "Sample Theory"
    assert proj.status == "active"

    # Area MainTopic created with parent_id=NULL.
    area = session.query(MainTopic).filter_by(code="0110EP").one()
    assert area.parent_id is None

    # Child MainTopic linked to area.
    child = proj.main_topic
    assert child.parent_id == area.id
    assert child.code == "0110EP26ST"

    # Directory structure on disk.
    expected_root = parent / "0110EP-26ST-SampleTheory"
    assert expected_root.is_dir()
    assert (expected_root / "config.yaml").is_file()
    assert (expected_root / "tex").is_dir()


def test_create_general_falls_through_initials_on_collision(session, tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    src = tmp_path / "src"
    src.mkdir()

    create_general(
        session,
        parent,
        src,
        title="Sample Theory",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )
    second = create_general(
        session,
        parent,
        src,
        title="Sample Thinking",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )
    # ST is taken → word1_prefix "SA"
    assert second.project_initials == "SA"
    assert (parent / "0110EP-26SA-SampleThinking").is_dir()


def test_create_general_explicit_pp_collision_raises(session, tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    src = tmp_path / "src"
    src.mkdir()

    create_general(
        session,
        parent,
        src,
        title="Sample Theory",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )
    with pytest.raises(click.ClickException, match="already taken"):
        create_general(
            session,
            parent,
            src,
            title="Other",
            year_init=26,
            project_initials="ST",
            area_code="0110EP",
            force_no_maturation=True,
        )


def test_create_general_unknown_area_raises(session, tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    src = tmp_path / "src"
    src.mkdir()
    with pytest.raises(click.ClickException, match="Unknown DisciplineArea"):
        create_general(
            session,
            parent,
            src,
            title="X",
            year_init=26,
            area_code="9999ZZ",
            force_no_maturation=True,
        )


def test_create_general_default_year_is_current(session, tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    src = tmp_path / "src"
    src.mkdir()
    proj = create_general(
        session,
        parent,
        src,
        title="Foo Bar",
        area_code="0110EP",
        force_no_maturation=True,
    )
    assert proj.year_init == date.today().year % 100


def test_create_general_reuses_existing_area_main_topic(session, tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    src = tmp_path / "src"
    src.mkdir()

    create_general(
        session,
        parent,
        src,
        title="First Project",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )
    create_general(
        session,
        parent,
        src,
        title="Second Effort",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )
    areas = session.query(MainTopic).filter_by(code="0110EP", parent_id=None).all()
    assert len(areas) == 1
    assert session.query(GeneralProject).count() == 2


# ── _create_dirs_from_tree: empty-topics guard (defect B) ──────────────


def test_create_dirs_from_tree_skips_placeholder_when_no_topics(tmp_path):
    _create_dirs_from_tree(tmp_path, ["a", "tex/{t_idx:03}-{t_name}"], [])

    assert (tmp_path / "a").is_dir()
    leftover_braces = list(tmp_path.rglob("*{*"))
    assert leftover_braces == []


def test_create_dirs_from_tree_expands_placeholder_when_topics_present(tmp_path):
    topics = [SimpleNamespace(name="Algebra"), SimpleNamespace(name="Calculus")]

    _create_dirs_from_tree(tmp_path, ["a", "tex/{t_idx:03}-{t_name}"], topics)

    assert (tmp_path / "a").is_dir()
    assert (tmp_path / "tex/001-Algebra").is_dir()
    assert (tmp_path / "tex/002-Calculus").is_dir()
    assert list(tmp_path.rglob("*{*")) == []


def test_create_general_with_no_topics_leaves_no_brace_paths(session, tmp_path):
    parent = tmp_path / "parent"
    src = tmp_path / "src"
    parent.mkdir()
    src.mkdir()

    proj = create_general(
        session,
        parent_dir=parent,
        src_dir=src,
        title="Brace Check",
        year_init=26,
        area_code="0110EP",
        force_no_maturation=True,
    )

    root = parent / proj.root_dir
    assert list(root.rglob("*{*")) == []


# ── LectureProject.tree: no malformed placeholders (defect C) ──────────


def test_lecture_project_tree_placeholders_are_well_formed():
    for entry in LectureProject.tree:
        if "{" in entry:
            entry.format(t_idx=1, t_name="x")
