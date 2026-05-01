"""Tests for workflow.db.schema_version (ITEP-0010)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase, LocalBase
from workflow.db.schema_version import (
    GlobalSchemaVersion,
    LocalSchemaVersion,
    applied_revisions,
    current_version,
    model_for,
    stamp,
)


@pytest.fixture
def gengine():
    engine = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def lengine():
    engine = create_engine("sqlite:///:memory:")
    LocalBase.metadata.create_all(engine)
    return engine


def test_global_schema_version_table_created(gengine):
    with Session(gengine) as s:
        assert s.query(GlobalSchemaVersion).all() == []


def test_local_schema_version_table_created(lengine):
    with Session(lengine) as s:
        assert s.query(LocalSchemaVersion).all() == []


def test_model_for_resolves_known_bases():
    assert model_for("global") is GlobalSchemaVersion
    assert model_for("local") is LocalSchemaVersion


def test_model_for_unknown_base_raises():
    with pytest.raises(ValueError):
        model_for("bogus")


def test_current_version_on_empty_returns_none(gengine):
    with Session(gengine) as s:
        assert current_version(s, "global") is None


def test_stamp_then_current_version(gengine):
    with Session(gengine) as s:
        stamp(s, "0001_baseline", "global")
        s.commit()
        assert current_version(s, "global") == "0001_baseline"


def test_current_version_returns_lexical_head(gengine):
    with Session(gengine) as s:
        stamp(s, "0002_second", "global")
        stamp(s, "0001_baseline", "global")
        s.commit()
        assert current_version(s, "global") == "0002_second"


def test_applied_revisions_sorted_lexically(gengine):
    with Session(gengine) as s:
        stamp(s, "0003_c", "global")
        stamp(s, "0001_a", "global")
        stamp(s, "0002_b", "global")
        s.commit()
        assert applied_revisions(s, "global") == ["0001_a", "0002_b", "0003_c"]


def test_global_and_local_stamps_independent(gengine, lengine):
    with Session(gengine) as gs, Session(lengine) as ls:
        stamp(gs, "0001_global", "global")
        gs.commit()
        assert current_version(ls, "local") is None
        stamp(ls, "0001_local", "local")
        ls.commit()
        assert current_version(gs, "global") == "0001_global"
        assert current_version(ls, "local") == "0001_local"


def test_stamp_unknown_base_raises(gengine):
    with Session(gengine) as s:
        with pytest.raises(ValueError):
            stamp(s, "0001_x", "wrong")
