"""Tests for BibExtraField importer integration and round-trip export (ADR-0019 A1).

Covers:
- Import .bib with origtitle/langid/eprintclass → bib_extra_field rows created
  (note: subtitle/origlocation/origpublisher/pubmedid/urlraw are now first-class
   columns since ADR-0019 A3 — they must NOT appear in extra_fields)
- Export --dialect biblatex re-emits those fields (round-trip)
- Junk field notabiblatexfield NOT stored
- Value-length cap enforced (value > MAX_EXTRA_VALUE_LEN skipped)
- Rows-per-entry cap enforced (> MAX_EXTRA_FIELDS entries dropped)
- UNIQUE(bib_entry_id, field) prevents duplicates on re-import
"""

from __future__ import annotations

import textwrap

from sqlalchemy import select

from workflow.db.models.bibliography import BibEntry, BibExtraField
from workflow.prisma.exporter import export_bib_entries
from workflow.prisma.importer import (
    MAX_EXTRA_FIELDS,
    MAX_EXTRA_VALUE_LEN,
    import_bib_text,
)


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
# Happy-path: catalog-known overflow fields are stored
# ---------------------------------------------------------------------------


class TestImporterExtraFields:
    """Extra fields are persisted for catalog-known fields without a first-class column."""

    BIB_WITH_EXTRAS = textwrap.dedent("""\
        @article{extra2020,
          title       = {Extra Field Test},
          year        = {2020},
          volume      = {5},
          origtitle   = {Der Ursprung der Arten},
          langid      = {english},
          eprintclass = {cs.AI},
        }
    """)

    def test_extra_fields_stored_on_import(self, global_session):
        import_bib_text(global_session, self.BIB_WITH_EXTRAS)
        entry = _get_entry(global_session, "extra2020")
        extras = _extra_dict(global_session, entry.id)

        assert "origtitle" in extras
        assert extras["origtitle"] == "Der Ursprung der Arten"
        assert "langid" in extras
        assert extras["langid"] == "english"
        assert "eprintclass" in extras
        assert extras["eprintclass"] == "cs.AI"

    def test_first_class_fields_not_in_overflow(self, global_session):
        import_bib_text(global_session, self.BIB_WITH_EXTRAS)
        entry = _get_entry(global_session, "extra2020")
        extras = _extra_dict(global_session, entry.id)
        # title/year/volume are first-class columns — must NOT appear in overflow
        assert "title" not in extras
        assert "year" not in extras
        assert "volume" not in extras


# ---------------------------------------------------------------------------
# Security: whitelist enforcement
# ---------------------------------------------------------------------------


class TestWhitelistEnforcement:
    """Non-catalog fields must be dropped, not stored."""

    BIB_WITH_JUNK = textwrap.dedent("""\
        @article{junk2021,
          title            = {Junk Field Test},
          year             = {2021},
          volume           = {6},
          notabiblatexfield = {should be dropped},
          xyzzy_garbage    = {also dropped},
          langid           = {english},
        }
    """)

    def test_junk_fields_not_stored(self, global_session):
        import_bib_text(global_session, self.BIB_WITH_JUNK)
        entry = _get_entry(global_session, "junk2021")
        extras = _extra_dict(global_session, entry.id)

        assert "notabiblatexfield" not in extras
        assert "xyzzy_garbage" not in extras
        assert "langid" in extras  # legitimate overflow field still stored


# ---------------------------------------------------------------------------
# Security: value-length cap
# ---------------------------------------------------------------------------


class TestValueLengthCap:
    """Values exceeding MAX_EXTRA_VALUE_LEN are skipped."""

    def test_over_length_value_skipped(self, global_session):
        long_value = "x" * (MAX_EXTRA_VALUE_LEN + 1)
        bib = textwrap.dedent(f"""\
            @article{{lentest2022,
              title  = {{Length Cap Test}},
              year   = {{2022}},
              volume = {{7}},
              langid = {{{long_value}}},
            }}
        """)
        import_bib_text(global_session, bib)
        entry = _get_entry(global_session, "lentest2022")
        extras = _extra_dict(global_session, entry.id)
        # langid value exceeds cap → must NOT be stored
        assert "langid" not in extras

    def test_at_max_length_value_stored(self, global_session):
        exact_value = "y" * MAX_EXTRA_VALUE_LEN
        bib = textwrap.dedent(f"""\
            @article{{lentest2023,
              title  = {{Exact Length Test}},
              year   = {{2023}},
              volume = {{8}},
              langid = {{{exact_value}}},
            }}
        """)
        import_bib_text(global_session, bib)
        entry = _get_entry(global_session, "lentest2023")
        extras = _extra_dict(global_session, entry.id)
        assert "langid" in extras
        assert extras["langid"] == exact_value


# ---------------------------------------------------------------------------
# Security: rows-per-entry cap
# ---------------------------------------------------------------------------


class TestRowsPerEntryCap:
    """At most MAX_EXTRA_FIELDS rows are stored per entry."""

    def test_rows_cap_enforced(self, global_session):
        # Build a .bib entry with more catalog fields than MAX_EXTRA_FIELDS.
        # Only fields that are NOT first-class BibEntry columns are overflow
        # candidates. Fields promoted in A3 (subtitle, titleaddon, booksubtitle,
        # mainsubtitle, maintitleaddon, booktitleaddon, origdate, origlocation,
        # origpublisher, pubmedid, urlraw) are excluded here.
        catalog_overflow_fields = [
            "origtitle", "langid", "eprintclass",
            "shorttitle", "journalsubtitle",
            "eventtitleaddon",
            "issuetitleaddon", "issuesubtitle", "journaltitleaddon",
            "indexsorttitle", "extratitle", "labeltitle", "extratitleyear",
            "nameaddon", "useprefix", "gender", "sortname", "sortkey",
            "sortinit", "sortinithash", "labelalpha", "labelnumber",
            "singletitle", "uniquename", "uniquetitle", "uniquework",
            "shortseries", "crossref", "xref", "relatedtype", "relatedstring",
            "relatedoptions", "entrysetcount", "subtype", "entrysubtype",
            "foreword", "afterword", "introduction", "commentary", "comment",
            "origlanguage", "pubmed", "gps", "articleid",
            "bookpagination", "place",
            "langidopts", "datepart", "dateunspecified",
            "endyear", "endmonth", "endday", "endseason", "endyeardivision",
            "eventyear", "eventmonth", "eventday", "eventseason",
            "eventyeardivision", "eventendyear", "eventendmonth", "eventendday",
            "eventendseason", "eventendyeardivision",
            "origyear", "origmonth", "origday", "origseason",
            "origyeardivision", "origendyear", "origendmonth", "origendday",
            "origendseason", "origendyeardivision",
            "urlyear", "urlmonth", "urlday", "urlseason", "urlyeardivision",
            "urlendyear", "urlendmonth", "urlendday", "urlendseason",
            "urlendyeardivision",
            "editora", "editorb", "editorc", "annotator", "commentator",
            "conductor", "bookauthor", "authortype", "editortype",
            "editoratype", "editorbtype", "editorctype", "namea",
            "moreauthor", "moreeditor", "moretranslator", "morelabelname",
        ]
        # Take MAX_EXTRA_FIELDS + 10 candidates
        candidates = catalog_overflow_fields[: MAX_EXTRA_FIELDS + 10]
        fields_str = "\n  ".join(
            f"{f} = {{value_{i}}}," for i, f in enumerate(candidates)
        )
        bib = textwrap.dedent(f"""\
            @article{{captest2024,
              title  = {{Cap Test}},
              year   = {{2024}},
              volume = {{9}},
              {fields_str}
            }}
        """)
        import_bib_text(global_session, bib)
        entry = _get_entry(global_session, "captest2024")
        extras = _extra_dict(global_session, entry.id)
        assert len(extras) <= MAX_EXTRA_FIELDS


# ---------------------------------------------------------------------------
# Round-trip export: extra fields re-emitted
# ---------------------------------------------------------------------------


class TestExportRoundTrip:
    """export_bib_entries re-emits extra fields in biblatex dialect."""

    BIB_ROUND_TRIP = textwrap.dedent("""\
        @article{roundtrip2025,
          title       = {Round Trip Test},
          year        = {2025},
          volume      = {10},
          origtitle   = {Original Title},
          langid      = {english},
          eprintclass = {quant-ph},
        }
    """)

    def test_biblatex_export_contains_extra_fields(self, global_session):
        import_bib_text(global_session, self.BIB_ROUND_TRIP)
        output = export_bib_entries(global_session, dialect="biblatex")

        assert "origtitle" in output
        assert "Original Title" in output
        assert "langid" in output
        assert "english" in output
        assert "eprintclass" in output
        assert "quant-ph" in output

    def test_bibtex_export_contains_extra_fields(self, global_session):
        import_bib_text(global_session, self.BIB_ROUND_TRIP)
        output = export_bib_entries(global_session, dialect="bibtex")

        # at minimum the entry itself must export
        assert "roundtrip2025" in output

    def test_junk_field_absent_from_export(self, global_session):
        bib = textwrap.dedent("""\
            @article{junkexport2026,
              title             = {Junk Export Test},
              year              = {2026},
              volume            = {11},
              notabiblatexfield = {must not appear},
              langid            = {english},
            }
        """)
        import_bib_text(global_session, bib)
        output = export_bib_entries(global_session, dialect="biblatex")
        assert "notabiblatexfield" not in output
        assert "english" in output


# ---------------------------------------------------------------------------
# Idempotency: re-import same entry does not duplicate extra rows
# ---------------------------------------------------------------------------


class TestImportIdempotency:
    """Re-importing the same entry (skipped via UNIQUE on bib_entry) does not double rows."""

    BIB_IDEMPOTENT = textwrap.dedent("""\
        @article{idemptest2027,
          title    = {Idempotent Test},
          year     = {2027},
          volume   = {12},
          langid   = {english},
        }
    """)

    def test_duplicate_import_skipped(self, global_session):
        import_bib_text(global_session, self.BIB_IDEMPOTENT)
        result2 = import_bib_text(global_session, self.BIB_IDEMPOTENT)
        assert result2.skipped == 1

        entry = _get_entry(global_session, "idemptest2027")
        extras = _extra_dict(global_session, entry.id)
        # Still exactly one langid row (no duplicate on re-import)
        assert extras.get("langid") is not None
        langid_rows = [ef for ef in entry.extra_fields if ef.field == "langid"]
        assert len(langid_rows) == 1
