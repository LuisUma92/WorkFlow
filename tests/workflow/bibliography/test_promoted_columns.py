"""Tests for Phase A3 — promoted first-class biblatex columns (ADR-0019 A3).

Covers:
1. Import: each promoted field lands in the BibEntry column, NOT in bib_extra_field.
2. Export biblatex: promoted fields round-trip via the column path.
3. read-both back-compat:
   a. Overflow-only entry (column NULL, extra_fields row present) → field still exported.
   b. Both column and overflow row present → column wins, field emitted exactly once.
4. Migration 0014 idempotency: double-apply is a no-op; all new columns present.
5. Dialect alias pmid → pubmedid round-trip.
"""

from __future__ import annotations

import importlib
import textwrap

from sqlalchemy import create_engine, select, text

from workflow.bibliography.dialect import BIBTEX_TO_BIBLATEX
from workflow.db.models.bibliography import BibEntry, BibExtraField
from workflow.prisma.exporter import export_bib_entries
from workflow.prisma.importer import _BIBENTRY_COLUMNS, import_bib_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_entry(session, bibkey: str) -> BibEntry:
    return session.execute(
        select(BibEntry).where(BibEntry.bibkey == bibkey)
    ).scalar_one()


def _extra_dict(session, entry_id: int) -> dict[str, str]:
    rows = session.scalars(
        select(BibExtraField).where(BibExtraField.bib_entry_id == entry_id)
    ).all()
    return {ef.field: ef.value for ef in rows}


# ---------------------------------------------------------------------------
# 1. Import: promoted fields land in columns, not overflow
# ---------------------------------------------------------------------------


class TestPromotedFieldsImportToColumns:
    """Each promoted field is assigned to its BibEntry column on import."""

    BIB_SUBTITLE_FAMILY = textwrap.dedent("""\
        @book{subtitletest2030,
          title          = {The Main Title},
          year           = {2030},
          volume         = {1},
          subtitle       = {A Fine Subtitle},
          titleaddon     = {Supplementary Note},
          booksubtitle   = {Book Sub},
          booktitleaddon = {Book Addon},
          mainsubtitle   = {Main Sub},
          maintitleaddon = {Main Addon},
        }
    """)

    BIB_ORIGIN_FAMILY = textwrap.dedent("""\
        @book{origintest2031,
          title          = {Reprinted Classic},
          year           = {2031},
          volume         = {2},
          origdate       = {1905},
          origlocation   = {Leipzig},
          origpublisher  = {Teubner},
        }
    """)

    BIB_IDENTIFIERS = textwrap.dedent("""\
        @article{identtest2032,
          title    = {Identifier Test},
          year     = {2032},
          volume   = {3},
          pubmedid = {12345678},
          urlraw   = {https://example.com/paper},
        }
    """)

    def test_subtitle_family_lands_in_columns(self, global_session):
        import_bib_text(global_session, self.BIB_SUBTITLE_FAMILY)
        entry = _get_entry(global_session, "subtitletest2030")
        extras = _extra_dict(global_session, entry.id)

        assert entry.subtitle == "A Fine Subtitle"
        assert entry.titleaddon == "Supplementary Note"
        assert entry.booksubtitle == "Book Sub"
        assert entry.booktitleaddon == "Book Addon"
        assert entry.mainsubtitle == "Main Sub"
        assert entry.maintitleaddon == "Main Addon"

        # Must NOT appear in overflow
        for field in ("subtitle", "titleaddon", "booksubtitle",
                      "booktitleaddon", "mainsubtitle", "maintitleaddon"):
            assert field not in extras, (
                f"{field!r} should be in the column, not bib_extra_field"
            )

    def test_origin_family_lands_in_columns(self, global_session):
        import_bib_text(global_session, self.BIB_ORIGIN_FAMILY)
        entry = _get_entry(global_session, "origintest2031")
        extras = _extra_dict(global_session, entry.id)

        assert entry.origdate == "1905"
        assert entry.origlocation == "Leipzig"
        assert entry.origpublisher == "Teubner"

        for field in ("origdate", "origlocation", "origpublisher"):
            assert field not in extras, (
                f"{field!r} should be in the column, not bib_extra_field"
            )

    def test_identifiers_land_in_columns(self, global_session):
        import_bib_text(global_session, self.BIB_IDENTIFIERS)
        entry = _get_entry(global_session, "identtest2032")
        extras = _extra_dict(global_session, entry.id)

        assert entry.pubmedid == "12345678"
        assert entry.urlraw == "https://example.com/paper"

        for field in ("pubmedid", "urlraw"):
            assert field not in extras, (
                f"{field!r} should be in the column, not bib_extra_field"
            )


# ---------------------------------------------------------------------------
# 2. Export round-trip via column path
# ---------------------------------------------------------------------------


class TestPromotedFieldsExportRoundTrip:
    """Promoted fields are emitted from BibEntry columns during export."""

    BIB_ALL_PROMOTED = textwrap.dedent("""\
        @book{exporttest2033,
          title          = {Export Round Trip},
          year           = {2033},
          volume         = {4},
          subtitle       = {Round-Trip Subtitle},
          origdate       = {1900},
          origlocation   = {Berlin},
          origpublisher  = {Springer},
          pubmedid       = {99887766},
          urlraw         = {https://doi.org/10.0000/test},
        }
    """)

    def test_biblatex_export_emits_promoted_fields(self, global_session):
        import_bib_text(global_session, self.BIB_ALL_PROMOTED)
        output = export_bib_entries(global_session, dialect="biblatex")

        assert "subtitle" in output
        assert "Round-Trip Subtitle" in output
        assert "origdate" in output
        assert "1900" in output
        assert "origlocation" in output
        assert "Berlin" in output
        assert "origpublisher" in output
        assert "Springer" in output
        assert "pubmedid" in output
        assert "99887766" in output
        assert "urlraw" in output
        assert "doi.org" in output

    def test_bibtex_export_emits_promoted_fields(self, global_session):
        import_bib_text(global_session, self.BIB_ALL_PROMOTED)
        output = export_bib_entries(global_session, dialect="bibtex")

        # biblatex-only fields (origdate, origpublisher, etc.) pass through
        # unchanged since they have no bibtex alias
        assert "exporttest2033" in output
        assert "Round-Trip Subtitle" in output


# ---------------------------------------------------------------------------
# 3. read-both back-compat (transition period)
# ---------------------------------------------------------------------------


class TestReadBothBackCompat:
    """Entries imported before A3 have the value in bib_extra_field (column=NULL).
    Export must still emit the field.  When BOTH exist, column wins, no double-emit.
    """

    def _make_entry(self, session, bibkey: str) -> BibEntry:
        entry = BibEntry(title="Back-Compat Test", year=2034, volume="5",
                         bibkey=bibkey)
        session.add(entry)
        session.flush()
        return entry

    def test_overflow_only_still_exported(self, global_session):
        """Column is NULL; value is only in bib_extra_field → must appear in export."""
        entry = self._make_entry(global_session, "backcompat2034a")
        # Simulate pre-A3 import: subtitle stored only in overflow
        global_session.add(BibExtraField(
            bib_entry_id=entry.id,
            field="subtitle",
            value="Legacy Subtitle",
        ))
        global_session.flush()
        assert entry.subtitle is None  # column null

        output = export_bib_entries(global_session, dialect="biblatex")
        assert "subtitle" in output
        assert "Legacy Subtitle" in output

    def test_column_wins_no_double_emit(self, global_session):
        """Both column and overflow row present → column value wins, emitted once."""
        entry = self._make_entry(global_session, "backcompat2034b")
        entry.subtitle = "Column Subtitle"
        global_session.flush()

        # Also plant a stale overflow row (simulates partial migration)
        global_session.add(BibExtraField(
            bib_entry_id=entry.id,
            field="subtitle",
            value="Overflow Subtitle",
        ))
        global_session.flush()

        output = export_bib_entries(global_session, dialect="biblatex")

        # Column value must appear
        assert "Column Subtitle" in output
        # Overflow value must NOT appear
        assert "Overflow Subtitle" not in output
        # Field emitted exactly once — count occurrences of the field line
        field_lines = [ln for ln in output.splitlines() if "subtitle" in ln]
        assert len(field_lines) == 1, (
            f"subtitle should appear exactly once in output, got {field_lines}"
        )


# ---------------------------------------------------------------------------
# 4. Migration 0014 idempotency
# ---------------------------------------------------------------------------


class TestMigration0014:
    """Migration 0014 must be idempotent and add all expected columns."""

    _EXPECTED_COLUMNS = {
        "subtitle", "titleaddon", "booksubtitle", "booktitleaddon",
        "mainsubtitle", "maintitleaddon",
        "origdate", "origlocation", "origpublisher",
        "pubmedid", "urlraw",
    }

    def _apply_migration(self, connection) -> None:
        mod = importlib.import_module(
            "workflow.db.migrations.global.0014_bib_promoted_columns"
        )
        mod.upgrade(connection)

    def _get_col_names(self, connection) -> set[str]:
        rows = connection.execute(text("PRAGMA table_info(bib_entry)")).fetchall()
        return {r[1] for r in rows}

    def _make_engine_with_bib_entry(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE bib_entry ("
                "  id INTEGER PRIMARY KEY,"
                "  title TEXT, year INTEGER, volume TEXT"
                ")"
            ))
        return engine

    def test_adds_all_expected_columns(self):
        engine = self._make_engine_with_bib_entry()
        with engine.begin() as conn:
            self._apply_migration(conn)
            cols = self._get_col_names(conn)
        for col in self._EXPECTED_COLUMNS:
            assert col in cols, f"column {col!r} missing after migration 0014"

    def test_idempotent_double_apply(self):
        engine = self._make_engine_with_bib_entry()
        with engine.begin() as conn:
            self._apply_migration(conn)
            # Second apply must not raise.
            self._apply_migration(conn)
            cols = self._get_col_names(conn)
        for col in self._EXPECTED_COLUMNS:
            assert col in cols

    def test_no_op_when_table_absent(self):
        """Migration must silently skip when bib_entry does not exist yet."""
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            # No bib_entry table created — must not raise
            self._apply_migration(conn)

    def test_revision_metadata(self):
        mod = importlib.import_module(
            "workflow.db.migrations.global.0014_bib_promoted_columns"
        )
        assert mod.revision == "0014_bib_promoted_columns"
        assert mod.base == "global"
        assert "A3" in mod.description or "promoted" in mod.description.lower()


# ---------------------------------------------------------------------------
# 5. Dialect alias pmid → pubmedid
# ---------------------------------------------------------------------------


class TestPmidAlias:
    """pmid is a JabRef/Zotero alias for biblatex pubmedid."""

    def test_pmid_in_bibtex_to_biblatex_map(self):
        assert "pmid" in BIBTEX_TO_BIBLATEX
        assert BIBTEX_TO_BIBLATEX["pmid"] == "pubmedid"

    def test_pmid_import_stores_in_pubmedid_column(self, global_session):
        bib = textwrap.dedent("""\
            @article{pmidtest2035,
              title  = {PMID Alias Test},
              year   = {2035},
              volume = {6},
              pmid   = {55556666},
            }
        """)
        import_bib_text(global_session, bib)
        entry = _get_entry(global_session, "pmidtest2035")
        assert entry.pubmedid == "55556666"

    def test_pmid_round_trip_biblatex_export(self, global_session):
        """pmid imported, exported as pubmedid in biblatex dialect."""
        bib = textwrap.dedent("""\
            @article{pmidrt2036,
              title  = {PMID Round Trip},
              year   = {2036},
              volume = {7},
              pmid   = {77778888},
            }
        """)
        import_bib_text(global_session, bib)
        output = export_bib_entries(global_session, dialect="biblatex")
        # Must appear as pubmedid (native biblatex name), not pmid
        assert "pubmedid" in output
        assert "77778888" in output
        # bibtex alias must not leak as a field (substring "pmid" also lives in
        # the citekey, so assert on the rendered field name, not raw substring).
        assert "pmid =" not in output and "pmid=" not in output

    def test_pubmedid_in_bibentry_columns(self):
        """pubmedid must be a first-class column (promoted in A3)."""
        assert "pubmedid" in _BIBENTRY_COLUMNS
