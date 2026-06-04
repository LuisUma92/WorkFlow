"""Tests for BibExtraField model and migration 0013 (ADR-0019 A1).

Covers:
- BibExtraField ORM model: creation, UNIQUE constraint, relationship
- Migration 0013 idempotency (apply twice = no error, no duplicate tables)
- Security constraints: value-length cap, rows-per-entry cap, whitelist enforcement
"""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from workflow.db.models.bibliography import BibEntry, BibExtraField
from workflow.prisma.importer import (
    MAX_EXTRA_FIELDS,
    MAX_EXTRA_VALUE_LEN,
    _BIBLATEX_FIELD_CATALOG,
    _BIBENTRY_COLUMNS,
)


# ---------------------------------------------------------------------------
# Catalog sanity tests
# ---------------------------------------------------------------------------


class TestFieldCatalog:
    """_BIBLATEX_FIELD_CATALOG integrity."""

    def test_catalog_is_frozenset(self):
        assert isinstance(_BIBLATEX_FIELD_CATALOG, frozenset)

    def test_catalog_non_empty(self):
        assert len(_BIBLATEX_FIELD_CATALOG) > 50

    def test_known_fields_present(self):
        for field in ("subtitle", "origtitle", "langid", "eprintclass", "shorttitle"):
            assert field in _BIBLATEX_FIELD_CATALOG, f"{field!r} missing from catalog"

    def test_aliases_present(self):
        for alias in ("archiveprefix", "primaryclass", "hyphenation", "pdf", "annote"):
            assert alias in _BIBLATEX_FIELD_CATALOG, f"alias {alias!r} missing from catalog"

    def test_junk_field_not_in_catalog(self):
        assert "notabiblatexfield" not in _BIBLATEX_FIELD_CATALOG
        assert "xyzzy_garbage" not in _BIBLATEX_FIELD_CATALOG

    def test_cap_constants(self):
        assert MAX_EXTRA_VALUE_LEN == 10_000
        assert MAX_EXTRA_FIELDS == 100

    def test_overflow_candidates_not_in_bibentry_columns(self):
        """Fields like subtitle/langid/eprintclass must be overflow (not first-class)."""
        overflow_fields = {"subtitle", "origtitle", "langid", "eprintclass"}
        for f in overflow_fields:
            assert f not in _BIBENTRY_COLUMNS, (
                f"{f!r} is already a first-class column; it should NOT go to overflow"
            )


# ---------------------------------------------------------------------------
# ORM model tests
# ---------------------------------------------------------------------------


class TestBibExtraFieldModel:
    """BibExtraField ORM model behaviour."""

    def test_create_extra_field(self, global_session):
        entry = BibEntry(title="Test Entry", year=2020, volume="1")
        global_session.add(entry)
        global_session.flush()

        ef = BibExtraField(bib_entry_id=entry.id, field="subtitle", value="A Subtitle")
        global_session.add(ef)
        global_session.flush()

        assert ef.id is not None
        assert ef.bib_entry_id == entry.id
        assert ef.field == "subtitle"
        assert ef.value == "A Subtitle"

    def test_relationship_back_populates(self, global_session):
        entry = BibEntry(title="Rel Test", year=2021, volume="2")
        global_session.add(entry)
        global_session.flush()

        for field, value in [("langid", "english"), ("origtitle", "Der Ursprung")]:
            global_session.add(BibExtraField(
                bib_entry_id=entry.id, field=field, value=value
            ))
        global_session.flush()
        global_session.refresh(entry)

        assert len(entry.extra_fields) == 2
        fields_stored = {ef.field for ef in entry.extra_fields}
        assert fields_stored == {"langid", "origtitle"}

    def test_unique_constraint_bib_entry_field(self, global_session):
        entry = BibEntry(title="UniqueTest", year=2022, volume="3")
        global_session.add(entry)
        global_session.flush()

        global_session.add(BibExtraField(
            bib_entry_id=entry.id, field="subtitle", value="First"
        ))
        global_session.flush()

        # Second insert of same (bib_entry_id, field) must violate UNIQUE.
        sp = global_session.begin_nested()
        try:
            global_session.add(BibExtraField(
                bib_entry_id=entry.id, field="subtitle", value="Second"
            ))
            global_session.flush()
            sp.commit()
            pytest.fail("Expected IntegrityError was not raised")
        except IntegrityError:
            sp.rollback()

    def test_repr(self, global_session):
        entry = BibEntry(title="Repr Test", year=2023, volume="4")
        global_session.add(entry)
        global_session.flush()
        ef = BibExtraField(bib_entry_id=entry.id, field="langid", value="german")
        global_session.add(ef)
        global_session.flush()
        assert "langid" in repr(ef)


# ---------------------------------------------------------------------------
# Migration 0013 idempotency
# ---------------------------------------------------------------------------


class TestMigration0013:
    """Migration 0013 must be idempotent and create the correct schema."""

    def _apply_migration(self, connection):
        mod = importlib.import_module(
            "workflow.db.migrations.global.0013_bib_extra_fields"
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
            # Create bib_entry first (FK target).
            conn.execute(text(
                "CREATE TABLE bib_entry (id INTEGER PRIMARY KEY, title TEXT, "
                "year INTEGER, volume TEXT)"
            ))
            self._apply_migration(conn)
            tables = self._get_tables(conn)
        assert "bib_extra_field" in tables

    def test_idempotent_double_apply(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE bib_entry (id INTEGER PRIMARY KEY, title TEXT, "
                "year INTEGER, volume TEXT)"
            ))
            self._apply_migration(conn)
            # Second apply must not raise.
            self._apply_migration(conn)
            tables = self._get_tables(conn)
        assert "bib_extra_field" in tables

    def test_schema_has_expected_columns(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE bib_entry (id INTEGER PRIMARY KEY, title TEXT, "
                "year INTEGER, volume TEXT)"
            ))
            self._apply_migration(conn)
            cols_info = conn.execute(
                text("PRAGMA table_info(bib_extra_field)")
            ).fetchall()
            col_names = {r[1] for r in cols_info}
        assert {"id", "bib_entry_id", "field", "value"}.issubset(col_names)

    def test_revision_and_description(self):
        mod = importlib.import_module(
            "workflow.db.migrations.global.0013_bib_extra_fields"
        )
        assert mod.revision == "0013_bib_extra_fields"
        assert "bib_extra_field" in mod.description
        assert mod.base == "global"
