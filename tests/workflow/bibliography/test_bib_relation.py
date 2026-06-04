"""Tests for the BibRelation model (Wave A — A4, ADR-0019).

BibRelation stores biblatex inter-entry relations (crossref/xref/xdata/related)
as (child, parent_bibkey, kind) rows. parent_id is resolved to a BibEntry when
the target exists; parent_bibkey is always preserved so the relation survives
even when the target is absent or a forward reference (lossless).
"""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from workflow.db.models.bibliography import BibEntry, BibRelation


def _make_entry(session, bibkey: str, title: str = "T") -> BibEntry:
    e = BibEntry(entry_type="article", bibkey=bibkey, title=title, year=2040)
    session.add(e)
    session.flush()
    return e


# ---------------------------------------------------------------------------
# Schema / columns
# ---------------------------------------------------------------------------


def test_bib_relation_columns_exist():
    cols = {c.name for c in BibRelation.__table__.columns}
    assert {"id", "child_id", "parent_bibkey", "parent_id", "kind"} <= cols


def test_parent_id_is_nullable():
    parent_col = BibRelation.__table__.columns["parent_id"]
    assert parent_col.nullable is True


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------


def test_create_and_load_via_relationship(global_session):
    child = _make_entry(global_session, "childA")
    parent = _make_entry(global_session, "parentA")
    rel = BibRelation(
        child_id=child.id,
        parent_bibkey="parentA",
        parent_id=parent.id,
        kind="crossref",
    )
    global_session.add(rel)
    global_session.flush()

    global_session.refresh(child)
    assert len(child.relations) == 1
    assert child.relations[0].kind == "crossref"
    assert child.relations[0].parent_bibkey == "parentA"
    assert child.relations[0].parent_id == parent.id


def test_unresolved_parent_keeps_bibkey(global_session):
    """parent_id NULL (target not imported) but parent_bibkey preserved."""
    child = _make_entry(global_session, "childB")
    rel = BibRelation(
        child_id=child.id,
        parent_bibkey="ghostparent",
        parent_id=None,
        kind="xref",
    )
    global_session.add(rel)
    global_session.flush()
    assert rel.parent_id is None
    assert rel.parent_bibkey == "ghostparent"


def test_unique_child_kind_parent(global_session):
    """Duplicate (child, kind, parent_bibkey) is rejected (idempotent re-import)."""
    child = _make_entry(global_session, "childC")
    global_session.add(
        BibRelation(child_id=child.id, parent_bibkey="p", kind="related")
    )
    global_session.flush()
    global_session.add(
        BibRelation(child_id=child.id, parent_bibkey="p", kind="related")
    )
    with pytest.raises(IntegrityError):
        global_session.flush()


def test_same_parent_different_kind_allowed(global_session):
    """A child may relate to the same parent under two different kinds."""
    child = _make_entry(global_session, "childD")
    global_session.add(
        BibRelation(child_id=child.id, parent_bibkey="p", kind="crossref")
    )
    global_session.add(
        BibRelation(child_id=child.id, parent_bibkey="p", kind="related")
    )
    global_session.flush()  # no IntegrityError
    global_session.refresh(child)
    assert len(child.relations) == 2


def test_cascade_delete_removes_relations(global_session):
    child = _make_entry(global_session, "childE")
    global_session.add(
        BibRelation(child_id=child.id, parent_bibkey="p", kind="xdata")
    )
    global_session.flush()
    global_session.delete(child)
    global_session.flush()
    remaining = global_session.query(BibRelation).filter_by(parent_bibkey="p").count()
    assert remaining == 0


# ---------------------------------------------------------------------------
# Migration 0015 idempotency
# ---------------------------------------------------------------------------


class TestMigration0015:
    """Migration 0015 must be idempotent and create the correct schema."""

    def _apply_migration(self, connection):
        mod = importlib.import_module(
            "workflow.db.migrations.global.0015_bib_relation"
        )
        mod.upgrade(connection)

    def _get_tables(self, connection) -> set[str]:
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        return {r[0] for r in rows}

    def test_creates_table(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE bib_entry (id INTEGER PRIMARY KEY)"))
            self._apply_migration(conn)
            tables = self._get_tables(conn)
        assert "bib_relation" in tables

    def test_idempotent_double_apply(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE bib_entry (id INTEGER PRIMARY KEY)"))
            self._apply_migration(conn)
            self._apply_migration(conn)  # must not raise
            tables = self._get_tables(conn)
        assert "bib_relation" in tables

    def test_schema_has_expected_columns(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE bib_entry (id INTEGER PRIMARY KEY)"))
            self._apply_migration(conn)
            cols_info = conn.execute(
                text("PRAGMA table_info(bib_relation)")
            ).fetchall()
            col_names = {r[1] for r in cols_info}
        assert {"id", "child_id", "parent_bibkey", "parent_id", "kind"} <= col_names

    def test_revision_and_description(self):
        mod = importlib.import_module(
            "workflow.db.migrations.global.0015_bib_relation"
        )
        assert mod.revision == "0015_bib_relation"
        assert "bib_relation" in mod.description
        assert mod.base == "global"

    def test_cleans_up_pre_a4_relation_overflow(self):
        """Pre-A4 crossref/xref/xdata/related rows in bib_extra_field are dropped."""
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE bib_entry (id INTEGER PRIMARY KEY)"))
            conn.execute(text(
                "CREATE TABLE bib_extra_field (id INTEGER PRIMARY KEY, "
                "bib_entry_id INTEGER, field VARCHAR(100), value TEXT)"
            ))
            conn.execute(text("INSERT INTO bib_entry (id) VALUES (1)"))
            for fld in ("crossref", "xref", "xdata", "related", "keepme"):
                conn.execute(text(
                    "INSERT INTO bib_extra_field (bib_entry_id, field, value) "
                    "VALUES (1, :f, 'v')"
                ), {"f": fld})
            self._apply_migration(conn)
            remaining = {
                r[0] for r in conn.execute(
                    text("SELECT field FROM bib_extra_field")
                ).fetchall()
            }
        assert remaining == {"keepme"}  # only the non-relation field survives
