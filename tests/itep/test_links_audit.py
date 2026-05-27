"""Tests for itep.links audit (--check) functionality."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea
from itep.create import create_general
from itep.defaults import (
    DEF_TEX_CONFIG,
    INSTITUTION_TEX_CONFIG,
    get_tex_config,
)
from itep.links import (
    LinkStatus,
    audit_symlink,
    iter_general_links,
    audit_links,
)


@pytest.fixture()
def session():
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


def test_audit_symlink_ok(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    assert audit_symlink(target, link).state == "OK"


def test_audit_symlink_missing(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "missing.txt"
    assert audit_symlink(target, link).state == "MISSING"


def test_audit_symlink_wrong_target(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("a")
    b = tmp_path / "b.txt"
    b.write_text("b")
    link = tmp_path / "link.txt"
    link.symlink_to(b)
    assert audit_symlink(a, link).state == "WRONG_TARGET"


def test_audit_symlink_broken(tmp_path):
    target = tmp_path / "ghost.txt"  # never created
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    assert audit_symlink(target, link).state == "BROKEN"


def test_audit_symlink_not_symlink(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link.txt"
    link.write_text("regular file")
    assert audit_symlink(target, link).state == "NOT_SYMLINK"


def test_iter_general_links_emits_config_entries(session, tmp_path):
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

    pairs = list(iter_general_links(proj))
    assert len(pairs) > 0, "expected at least DEF_TEX_CONFIG entries"
    # all link paths under project root/config
    root = Path(proj.abs_parent_dir) / proj.root_dir
    for _target, link_path in pairs:
        assert str(link_path).startswith(str(root))


def test_get_tex_config_unknown_institution_returns_default():
    assert get_tex_config(None) is DEF_TEX_CONFIG
    assert get_tex_config("UNKNOWN_INST") is DEF_TEX_CONFIG
    # UCR now has a specialized config
    assert get_tex_config("UCR") is INSTITUTION_TEX_CONFIG["UCR"]


def test_get_tex_config_ucimed_uses_underscore_scheme():
    cfg = get_tex_config("UCIMED")
    assert cfg is INSTITUTION_TEX_CONFIG["UCIMED"]
    assert "0_packages.sty" in cfg
    # legacy hyphen names must NOT be present in UCIMED dict
    assert "0-packages.sty" not in cfg


def test_def_tex_config_targets_xdg_pool():
    # Sanity: default targets should resolve under ~/.local/share/workflow/sty
    assert any("/.local/share/workflow/sty/" in v for v in DEF_TEX_CONFIG.values())


def test_audit_links_reports_all_missing_for_fresh_project(session, tmp_path):
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

    statuses = audit_links(iter_general_links(proj))
    # No symlinks created yet → all MISSING.
    assert all(isinstance(s, LinkStatus) for s in statuses)
    assert all(s.state == "MISSING" for s in statuses)
