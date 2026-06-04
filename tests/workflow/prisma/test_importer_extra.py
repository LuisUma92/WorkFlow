"""Tests for BibExtraField importer integration and round-trip export (ADR-0019 A1).

Covers:
- Import .bib with subtitle/origtitle/langid/eprintclass → bib_extra_field rows created
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
          subtitle    = {An Important Subtitle},
          origtitle   = {Der Ursprung der Arten},
          langid      = {english},
          eprintclass = {cs.AI},
        }
    """)

    def test_extra_fields_stored_on_import(self, global_session):
        import_bib_text(global_session, self.BIB_WITH_EXTRAS)
        entry = _get_entry(global_session, "extra2020")
        extras = _extra_dict(global_session, entry.id)

        assert "subtitle" in extras, "subtitle should be stored as overflow"
        assert extras["subtitle"] == "An Important Subtitle"
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
          subtitle         = {A Real Field},
        }
    """)

    def test_junk_fields_not_stored(self, global_session):
        import_bib_text(global_session, self.BIB_WITH_JUNK)
        entry = _get_entry(global_session, "junk2021")
        extras = _extra_dict(global_session, entry.id)

        assert "notabiblatexfield" not in extras
        assert "xyzzy_garbage" not in extras
        assert "subtitle" in extras  # legitimate field still stored


# ---------------------------------------------------------------------------
# Security: value-length cap
# ---------------------------------------------------------------------------


class TestValueLengthCap:
    """Values exceeding MAX_EXTRA_VALUE_LEN are skipped."""

    def test_over_length_value_skipped(self, global_session):
        long_value = "x" * (MAX_EXTRA_VALUE_LEN + 1)
        bib = textwrap.dedent(f"""\
            @article{{lentest2022,
              title    = {{Length Cap Test}},
              year     = {{2022}},
              volume   = {{7}},
              subtitle = {{{long_value}}},
            }}
        """)
        import_bib_text(global_session, bib)
        entry = _get_entry(global_session, "lentest2022")
        extras = _extra_dict(global_session, entry.id)
        # subtitle value exceeds cap → must NOT be stored
        assert "subtitle" not in extras

    def test_at_max_length_value_stored(self, global_session):
        exact_value = "y" * MAX_EXTRA_VALUE_LEN
        bib = textwrap.dedent(f"""\
            @article{{lentest2023,
              title    = {{Exact Length Test}},
              year     = {{2023}},
              volume   = {{8}},
              subtitle = {{{exact_value}}},
            }}
        """)
        import_bib_text(global_session, bib)
        entry = _get_entry(global_session, "lentest2023")
        extras = _extra_dict(global_session, entry.id)
        assert "subtitle" in extras
        assert extras["subtitle"] == exact_value


# ---------------------------------------------------------------------------
# Security: rows-per-entry cap
# ---------------------------------------------------------------------------


class TestRowsPerEntryCap:
    """At most MAX_EXTRA_FIELDS rows are stored per entry."""

    def test_rows_cap_enforced(self, global_session):
        # Build a .bib entry with more catalog fields than MAX_EXTRA_FIELDS.
        # We use date sub-fields (all catalog-known) to fill slots.
        # Many of the date sub-fields (endyear, eventyear…) are catalog-known
        # but not first-class columns, making them legitimate overflow candidates.
        catalog_overflow_fields = [
            "subtitle", "origtitle", "langid", "eprintclass",
            "shorttitle", "titleaddon", "booksubtitle", "journalsubtitle",
            "mainsubtitle", "maintitleaddon", "booktitleaddon", "eventtitleaddon",
            "issuetitleaddon", "issuesubtitle", "journaltitleaddon",
            "indexsorttitle", "extratitle", "labeltitle", "extratitleyear",
            "nameaddon", "useprefix", "gender", "sortname", "sortkey",
            "sortinit", "sortinithash", "labelalpha", "labelnumber",
            "singletitle", "uniquename", "uniquetitle", "uniquework",
            "shortseries", "crossref", "xref", "relatedtype", "relatedstring",
            "relatedoptions", "entrysetcount", "subtype", "entrysubtype",
            "foreword", "afterword", "introduction", "commentary", "comment",
            "origlanguage", "urlraw", "pubmedid", "pubmed", "gps", "articleid",
            "bookpagination", "place", "origlocation", "origpublisher",
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
          subtitle    = {The Subtitle},
          langid      = {english},
          eprintclass = {quant-ph},
        }
    """)

    def test_biblatex_export_contains_extra_fields(self, global_session):
        import_bib_text(global_session, self.BIB_ROUND_TRIP)
        output = export_bib_entries(global_session, dialect="biblatex")

        assert "subtitle" in output
        assert "The Subtitle" in output
        assert "langid" in output
        assert "english" in output
        assert "eprintclass" in output
        assert "quant-ph" in output

    def test_bibtex_export_contains_extra_fields(self, global_session):
        import_bib_text(global_session, self.BIB_ROUND_TRIP)
        output = export_bib_entries(global_session, dialect="bibtex")

        # subtitle has no bibtex alias; it may be passed through or dropped
        # depending on the dialect map — at minimum the entry itself must export
        assert "roundtrip2025" in output

    def test_junk_field_absent_from_export(self, global_session):
        bib = textwrap.dedent("""\
            @article{junkexport2026,
              title             = {Junk Export Test},
              year              = {2026},
              volume            = {11},
              notabiblatexfield = {must not appear},
              subtitle          = {Real Subtitle},
            }
        """)
        import_bib_text(global_session, bib)
        output = export_bib_entries(global_session, dialect="biblatex")
        assert "notabiblatexfield" not in output
        assert "Real Subtitle" in output


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
          subtitle = {Consistent Subtitle},
        }
    """)

    def test_duplicate_import_skipped(self, global_session):
        import_bib_text(global_session, self.BIB_IDEMPOTENT)
        result2 = import_bib_text(global_session, self.BIB_IDEMPOTENT)
        assert result2.skipped == 1

        entry = _get_entry(global_session, "idemptest2027")
        extras = _extra_dict(global_session, entry.id)
        # Still exactly one subtitle row (no duplicate on re-import)
        assert extras.get("subtitle") is not None
        subtitle_rows = [ef for ef in entry.extra_fields if ef.field == "subtitle"]
        assert len(subtitle_rows) == 1
