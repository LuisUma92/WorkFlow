"""Tests for ADR-0019 Phase 3 — biblatex/bibtex dialect exporter.

Covers:
- _entry_to_biblatex: emits canonical biblatex field names
- _entry_to_bibtex: reverse-maps journaltitle→journal, location→address, etc.
- Entry type downgrade table: online→misc, report→techreport, thesis→phdthesis/mastersthesis
- author name_prefix (von) / name_suffix (jr) in each dialect
- Round-trip: biblatex import → export --dialect biblatex is field-equivalent
- CLI: prisma bib export --dialect biblatex|bibtex flag
"""

from __future__ import annotations

import textwrap

import pytest
from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import Author, AuthorType, BibAuthor, BibEntry, IsnType
from workflow.prisma.cli import prisma
from workflow.prisma.exporter import _entry_to_biblatex, _entry_to_bibtex, export_bib_entries
from workflow.prisma.importer import import_bib_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(session: Session, **kwargs) -> BibEntry:
    """Create a bare BibEntry (no authors) flushed into session."""
    defaults: dict = dict(
        entry_type="article",
        bibkey="testbib",
        title="Test Title",
        year=2020,
        volume="1",
    )
    defaults.update(kwargs)
    e = BibEntry(**defaults)
    session.add(e)
    session.flush()
    return e


# ---------------------------------------------------------------------------
# Unit: _entry_to_biblatex field names
# ---------------------------------------------------------------------------


class TestEntryToBiblatex:
    """_entry_to_biblatex emits canonical biblatex field names."""

    def test_journaltitle_emitted_directly(self, global_session):
        e = _make_entry(global_session, bibkey="jt1", journaltitle="Phys Rev", volume="2")
        block = _entry_to_biblatex(e)
        assert "journaltitle =" in block
        assert "journal =" not in block

    def test_location_emitted_directly(self, global_session):
        e = _make_entry(global_session, bibkey="loc1", location="Berlin", volume="3")
        block = _entry_to_biblatex(e)
        assert "location" in block
        assert "address" not in block

    def test_institution_emitted_directly(self, global_session):
        e = _make_entry(global_session, bibkey="ins1", institution="MIT", volume="4")
        block = _entry_to_biblatex(e)
        assert "institution" in block
        assert "school" not in block

    def test_annotation_emitted_directly(self, global_session):
        e = _make_entry(global_session, bibkey="ann1", annotation="My note", volume="5")
        block = _entry_to_biblatex(e)
        assert "annotation" in block
        assert "annote" not in block

    def test_notes_emitted_directly(self, global_session):
        e = _make_entry(global_session, bibkey="nts1", notes="See also", volume="6")
        block = _entry_to_biblatex(e)
        assert "notes" in block
        assert "note =" not in block  # 'note' is not the canonical name

    def test_date_field_emitted(self, global_session):
        e = _make_entry(global_session, bibkey="dt1", date="2010/2015", volume="7")
        block = _entry_to_biblatex(e)
        assert "date" in block
        assert "2010/2015" in block

    def test_chapter_emitted(self, global_session):
        e = _make_entry(global_session, bibkey="ch1", chapter="3", volume="8")
        block = _entry_to_biblatex(e)
        assert "chapter" in block

    def test_type_field_emitted(self, global_session):
        e = _make_entry(global_session, bibkey="tp1", entry_type="report",
                        type="Technical Report", volume="9")
        block = _entry_to_biblatex(e)
        assert "type" in block
        assert "@report{" in block

    def test_entry_type_not_downgraded(self, global_session):
        """biblatex export keeps @online as-is."""
        e = _make_entry(global_session, bibkey="on1", entry_type="online", volume="10")
        block = _entry_to_biblatex(e)
        assert block.startswith("@online{")

    def test_isn_without_type_emitted_as_isn(self, global_session):
        """isn without isn_type falls back to field name 'isn'."""
        e = _make_entry(global_session, bibkey="isn1", isn="978-3-16-148410-0", volume="11")
        block = _entry_to_biblatex(e)
        assert "isn = {978-3-16-148410-0}" in block

    def test_isbn_dispatched_from_isn_type(self, global_session):
        """isn + isn_type.code='isbn' → emitted as 'isbn = {...}'."""
        isn_type = IsnType(code="isbn")
        global_session.add(isn_type)
        global_session.flush()
        e = _make_entry(global_session, bibkey="isbn1", isn="978-3-16-148410-0",
                        isn_type_id=isn_type.id, volume="11b")
        e.isn_type = isn_type
        block = _entry_to_biblatex(e)
        assert "isbn = {978-3-16-148410-0}" in block
        assert "isn =" not in block


# ---------------------------------------------------------------------------
# Unit: _entry_to_bibtex field name reverse-mapping
# ---------------------------------------------------------------------------


class TestEntryToBibtex:
    """_entry_to_bibtex reverse-maps biblatex field names to bibtex aliases."""

    def test_journaltitle_becomes_journal(self, global_session):
        e = _make_entry(global_session, bibkey="jt2", journaltitle="Phys Rev", volume="12")
        block = _entry_to_bibtex(e)
        assert "journal = {Phys Rev}" in block
        assert "journaltitle" not in block

    def test_location_becomes_address(self, global_session):
        e = _make_entry(global_session, bibkey="loc2", location="Berlin", volume="13")
        block = _entry_to_bibtex(e)
        assert "address = {Berlin}" in block
        assert "location" not in block

    def test_institution_becomes_school(self, global_session):
        e = _make_entry(global_session, bibkey="ins2", institution="MIT", volume="14")
        block = _entry_to_bibtex(e)
        assert "school = {MIT}" in block
        assert "institution" not in block

    def test_annotation_becomes_annote(self, global_session):
        e = _make_entry(global_session, bibkey="ann2", annotation="My note", volume="15")
        block = _entry_to_bibtex(e)
        assert "annote = {My note}" in block
        assert "annotation" not in block

    def test_notes_becomes_note(self, global_session):
        e = _make_entry(global_session, bibkey="nts2", notes="See also", volume="16")
        block = _entry_to_bibtex(e)
        assert "note = {See also}" in block
        assert "notes" not in block

    def test_date_range_split_to_year(self, global_session):
        """date=2010/2015 → year=2010 in bibtex output (derived year column used)."""
        e = _make_entry(global_session, bibkey="dr1", date="2010/2015",
                        year=2010, volume="17")
        block = _entry_to_bibtex(e)
        assert "year = {2010}" in block
        assert "date" not in block

    def test_date_single_year_not_duplicated(self, global_session):
        """When year column exists, date not re-emitted in bibtex."""
        e = _make_entry(global_session, bibkey="dr2", date="2020",
                        year=2020, volume="18")
        block = _entry_to_bibtex(e)
        assert "year = {2020}" in block
        assert "date" not in block


# ---------------------------------------------------------------------------
# Unit: entry type downgrade table
# ---------------------------------------------------------------------------


class TestEntryTypeDowngrade:
    """_entry_to_bibtex downgrades biblatex-only entry types."""

    def test_online_becomes_misc(self, global_session):
        e = _make_entry(global_session, bibkey="on2", entry_type="online", volume="20")
        block = _entry_to_bibtex(e)
        assert block.startswith("@misc{")

    def test_online_gets_howpublished(self, global_session):
        """@online with url → howpublished=\\url{...} injected in bibtex output."""
        from workflow.db.models.bibliography import BibUrl, ReferencedDatabase
        e = _make_entry(global_session, bibkey="on3", entry_type="online",
                        doi=None, volume="21")
        db = ReferencedDatabase(name="TestDB")
        global_session.add(db)
        global_session.flush()
        burl = BibUrl(bib_entry_id=e.id, database_id=db.id,
                      url_string="https://example.com/article", main_url=True)
        global_session.add(burl)
        global_session.flush()
        block = _entry_to_bibtex(e)
        assert "@misc{" in block
        assert "howpublished" in block
        assert "https://example.com/article" in block

    def test_report_becomes_techreport(self, global_session):
        e = _make_entry(global_session, bibkey="rp1", entry_type="report", volume="22")
        block = _entry_to_bibtex(e)
        assert block.startswith("@techreport{")

    def test_thesis_phdthesis_by_default(self, global_session):
        """@thesis with no type field → @phdthesis."""
        e = _make_entry(global_session, bibkey="th1", entry_type="thesis", volume="23")
        block = _entry_to_bibtex(e)
        assert block.startswith("@phdthesis{")

    def test_thesis_mastersthesis_by_type(self, global_session):
        """@thesis with type='mathesis' or 'Master*' → @mastersthesis."""
        e = _make_entry(global_session, bibkey="th2", entry_type="thesis",
                        type="mathesis", volume="24")
        block = _entry_to_bibtex(e)
        assert block.startswith("@mastersthesis{")

    def test_thesis_mastersthesis_by_master_keyword(self, global_session):
        """@thesis with type containing 'master' (case-insensitive) → @mastersthesis."""
        e = _make_entry(global_session, bibkey="th3", entry_type="thesis",
                        type="Master Thesis", volume="25")
        block = _entry_to_bibtex(e)
        assert block.startswith("@mastersthesis{")

    def test_mvbook_becomes_book(self, global_session):
        """biblatex-only @mvbook → @book in bibtex export."""
        e = _make_entry(global_session, bibkey="mv1", entry_type="mvbook", volume="26")
        block = _entry_to_bibtex(e)
        assert block.startswith("@book{")

    def test_inreference_becomes_inbook(self, global_session):
        """@inreference → @inbook in bibtex export."""
        e = _make_entry(global_session, bibkey="ir1", entry_type="inreference", volume="27")
        block = _entry_to_bibtex(e)
        assert block.startswith("@inbook{")

    def test_known_bibtex_type_unchanged(self, global_session):
        """Standard bibtex types (article, book, inproceedings) pass through."""
        e = _make_entry(global_session, bibkey="ar2", entry_type="article", volume="28")
        block = _entry_to_bibtex(e)
        assert block.startswith("@article{")


# ---------------------------------------------------------------------------
# Unit: author formatting with prefix/suffix
# ---------------------------------------------------------------------------


class TestAuthorFormatting:
    """Author with name_prefix (von) and name_suffix (jr) emit correctly."""

    def _make_entry_with_author(
        self, session: Session, *,
        first: str, last: str,
        prefix: str | None = None, suffix: str | None = None,
        bibkey: str = "authtest",
        volume: str = "30",
    ) -> BibEntry:
        entry = _make_entry(session, bibkey=bibkey, volume=volume)
        at = session.execute(
            select(AuthorType).where(AuthorType.type_of_author == "author")
        ).scalar_one_or_none()
        if at is None:
            at = AuthorType(type_of_author="author")
            session.add(at)
            session.flush()
        author = Author(first_name=first, last_name=last,
                        name_prefix=prefix, name_suffix=suffix)
        session.add(author)
        session.flush()
        link = BibAuthor(bib_entry_id=entry.id, author_id=author.id,
                         author_type_id=at.id, first_author=True)
        session.add(link)
        session.flush()
        return entry

    def test_biblatex_author_with_prefix_von_form(self, global_session):
        """biblatex: 'von Last, First' form when prefix present."""
        e = self._make_entry_with_author(
            global_session, first="Ludwig", last="Beethoven",
            prefix="van", bibkey="vontest1", volume="31",
        )
        block = _entry_to_biblatex(e)
        assert "author" in block
        assert "van" in block

    def test_biblatex_author_with_suffix_jr_form(self, global_session):
        """biblatex: 'Last, Jr, First' form when suffix present."""
        e = self._make_entry_with_author(
            global_session, first="John", last="Smith",
            suffix="Jr.", bibkey="jrtest1", volume="32",
        )
        block = _entry_to_biblatex(e)
        assert "author" in block
        assert "Jr." in block

    def test_bibtex_author_with_prefix_emitted(self, global_session):
        """bibtex: prefix (von) included in author string."""
        e = self._make_entry_with_author(
            global_session, first="Ludwig", last="Beethoven",
            prefix="van", bibkey="vontest2", volume="33",
        )
        block = _entry_to_bibtex(e)
        assert "author" in block
        assert "van" in block

    def test_bibtex_author_with_suffix_emitted(self, global_session):
        """bibtex: suffix (jr) included in author string."""
        e = self._make_entry_with_author(
            global_session, first="John", last="Smith",
            suffix="Jr.", bibkey="jrtest2", volume="34",
        )
        block = _entry_to_bibtex(e)
        assert "author" in block
        assert "Jr." in block

    def test_plain_author_no_prefix_suffix(self, global_session):
        """Plain 'Last, First' when no prefix/suffix."""
        e = self._make_entry_with_author(
            global_session, first="Alice", last="Walker",
            bibkey="plain1", volume="35",
        )
        block = _entry_to_biblatex(e)
        assert "Walker, Alice" in block


# ---------------------------------------------------------------------------
# Round-trip: biblatex import → export --dialect biblatex
# ---------------------------------------------------------------------------


class TestRoundTripBiblatex:
    """Import a biblatex entry, export with dialect=biblatex, check field equivalence."""

    _BIB = textwrap.dedent("""\
        @article{roundtrip2023,
          title        = {Round Trip Article},
          author       = {van Beethoven, Ludwig},
          journaltitle = {Physics Letters},
          location     = {Berlin},
          institution  = {TU Berlin},
          annotation   = {Great paper},
          notes        = {See appendix},
          date         = {2023},
          year         = {2023},
          volume       = {42},
        }
    """)

    def test_journaltitle_survives_round_trip(self, global_session):
        import_bib_text(global_session, self._BIB)
        result = export_bib_entries(global_session, dialect="biblatex")
        assert "journaltitle = {Physics Letters}" in result

    def test_location_survives_round_trip(self, global_session):
        import_bib_text(global_session, self._BIB)
        result = export_bib_entries(global_session, dialect="biblatex")
        assert "location = {Berlin}" in result

    def test_annotation_survives_round_trip(self, global_session):
        import_bib_text(global_session, self._BIB)
        result = export_bib_entries(global_session, dialect="biblatex")
        assert "annotation = {Great paper}" in result

    def test_notes_survives_round_trip(self, global_session):
        import_bib_text(global_session, self._BIB)
        result = export_bib_entries(global_session, dialect="biblatex")
        assert "notes = {See appendix}" in result

    def test_entry_type_preserved_biblatex(self, global_session):
        import_bib_text(global_session, self._BIB)
        result = export_bib_entries(global_session, dialect="biblatex")
        assert "@article{" in result


class TestRoundTripBibtex:
    """Import a biblatex entry, export with dialect=bibtex, check downgrade."""

    _BIB = textwrap.dedent("""\
        @online{webref2024,
          title  = {Web Reference},
          author = {Doe, Jane},
          url    = {https://example.com},
          year   = {2024},
          volume = {50},
        }
    """)

    _REPORT_BIB = textwrap.dedent("""\
        @report{techreport2024,
          title       = {Tech Report},
          author      = {Doe, John},
          institution = {ACME Inc},
          year        = {2024},
          volume      = {51},
        }
    """)

    def test_online_exported_as_misc(self, global_session):
        import_bib_text(global_session, self._BIB)
        result = export_bib_entries(global_session, dialect="bibtex")
        assert "@misc{" in result
        assert "@online{" not in result

    def test_report_exported_as_techreport(self, global_session):
        import_bib_text(global_session, self._REPORT_BIB)
        result = export_bib_entries(global_session, dialect="bibtex")
        assert "@techreport{" in result
        assert "@report{" not in result

    def test_bibtex_has_journal_not_journaltitle(self, global_session):
        bib = textwrap.dedent("""\
            @article{art2024,
              title        = {A Paper},
              author       = {Smith, Alice},
              journaltitle = {Nature},
              year         = {2024},
              volume       = {52},
            }
        """)
        import_bib_text(global_session, bib)
        result = export_bib_entries(global_session, dialect="bibtex")
        assert "journal = {Nature}" in result
        assert "journaltitle" not in result


# ---------------------------------------------------------------------------
# export_bib_entries: dialect parameter
# ---------------------------------------------------------------------------


class TestExportBibEntriesDialect:
    def test_default_dialect_is_biblatex(self, global_session):
        """Calling without dialect= defaults to biblatex output."""
        bib = textwrap.dedent("""\
            @article{deftest,
              title        = {Default Test},
              journaltitle = {Science},
              year         = {2021},
              volume       = {60},
            }
        """)
        import_bib_text(global_session, bib)
        result = export_bib_entries(global_session)
        assert "journaltitle" in result

    def test_bibtex_dialect_arg(self, global_session):
        bib = textwrap.dedent("""\
            @article{bttest,
              title        = {Bibtex Test},
              journaltitle = {Nature},
              year         = {2022},
              volume       = {61},
            }
        """)
        import_bib_text(global_session, bib)
        result = export_bib_entries(global_session, dialect="bibtex")
        assert "journal = {Nature}" in result


# ---------------------------------------------------------------------------
# CLI: prisma bib export --dialect
# ---------------------------------------------------------------------------


class TestCliExportDialect:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def seeded_engine(self, global_engine):
        bib = textwrap.dedent("""\
            @article{clitest2023,
              title        = {CLI Test},
              author       = {Doe, Jane},
              journaltitle = {JOSS},
              location     = {NYC},
              year         = {2023},
              volume       = {70},
            }
        """)
        with Session(global_engine) as s:
            import_bib_text(s, bib)
        return global_engine

    def _invoke(self, runner, engine, extra_args=None):
        args = ["bib", "export"] + (extra_args or [])
        return runner.invoke(
            prisma, args, obj={"engine": engine}, catch_exceptions=False
        )

    def test_default_no_flag_gives_biblatex(self, runner, seeded_engine):
        r = self._invoke(runner, seeded_engine)
        assert r.exit_code == 0
        assert "journaltitle" in r.output

    def test_dialect_biblatex_explicit(self, runner, seeded_engine):
        r = self._invoke(runner, seeded_engine, ["--dialect", "biblatex"])
        assert r.exit_code == 0
        assert "journaltitle" in r.output

    def test_dialect_bibtex_flag(self, runner, seeded_engine):
        r = self._invoke(runner, seeded_engine, ["--dialect", "bibtex"])
        assert r.exit_code == 0
        assert "journal = {JOSS}" in r.output
        assert "journaltitle" not in r.output

    def test_dialect_bibtex_reverses_location(self, runner, seeded_engine):
        r = self._invoke(runner, seeded_engine, ["--dialect", "bibtex"])
        assert r.exit_code == 0
        assert "address = {NYC}" in r.output
        assert "location" not in r.output

    def test_invalid_dialect_fails(self, runner, seeded_engine):
        r = self._invoke(runner, seeded_engine, ["--dialect", "badvalue"])
        assert r.exit_code != 0

    def test_status_requires_keyword_id_still_enforced(self, runner, seeded_engine):
        r = self._invoke(runner, seeded_engine,
                         ["--status", "included", "--dialect", "bibtex"])
        assert r.exit_code != 0
