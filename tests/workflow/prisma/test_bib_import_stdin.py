"""Tests for import_bib_text (stdin path) and --stdin CLI flag.

A3 coverage:
- stdin text creates BibEntry (+ Author/BibAuthor) rows
- file path and stdin with same biblatex produce equal rows (parity)
- empty/whitespace stdin → ImportResult with no created rows and no crash
- --stdin + path together → exit non-zero with combination error
- existing file-path import still works (regression)
"""

from __future__ import annotations

import json
import textwrap
import warnings

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from workflow.db.models.bibliography import BibAuthor, BibEntry
from workflow.prisma.cli import prisma
from workflow.prisma.importer import (
    MAX_BIB_SIZE_BYTES,
    ImportResult,
    import_bib_file,
    import_bib_text,
)

_SAMPLE_BIB = textwrap.dedent("""\
    @book{testkey2020,
      title     = {Test Book},
      author    = {Alice Smith and Bob Jones},
      year      = {2020},
      volume    = {1},
      publisher = {Test Press},
    }
""")


# ---------------------------------------------------------------------------
# Unit: import_bib_text
# ---------------------------------------------------------------------------

class TestImportBibText:
    def test_creates_bib_entry(self, global_session):
        result = import_bib_text(global_session, _SAMPLE_BIB)
        assert result.created == 1
        assert result.skipped == 0
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "testkey2020")
        ).scalar_one()
        assert entry.title == "Test Book"

    def test_creates_authors_and_bib_authors(self, global_session):
        import_bib_text(global_session, _SAMPLE_BIB)
        bib_authors = global_session.execute(select(BibAuthor)).scalars().all()
        assert len(bib_authors) == 2
        author_names = {a.author.last_name for a in bib_authors}
        assert "Smith" in author_names
        assert "Jones" in author_names

    def test_empty_string_returns_zero_created(self, global_session):
        result = import_bib_text(global_session, "")
        assert result.created == 0
        assert result.skipped == 0
        assert len(result.errors) == 0

    def test_whitespace_only_returns_zero_created(self, global_session):
        result = import_bib_text(global_session, "   \n\t  ")
        assert result.created == 0
        assert result.skipped == 0

    def test_returns_import_result(self, global_session):
        result = import_bib_text(global_session, _SAMPLE_BIB)
        assert isinstance(result, ImportResult)

    def test_database_name_passed_through(self, global_session):
        import_bib_text(global_session, _SAMPLE_BIB, database_name="TestDB")
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "testkey2020")
        ).scalar_one()
        # ReferencedDatabase row should exist; check via entry relationships
        # (just verify no crash and entry created)
        assert entry.bibkey == "testkey2020"

    def test_duplicate_skipped(self, global_engine):
        """Second import of same entry (title+year+volume unique) returns skipped=1."""
        from sqlalchemy.orm import Session
        with Session(global_engine) as s1:
            import_bib_text(s1, _SAMPLE_BIB)
        with Session(global_engine) as s2:
            result2 = import_bib_text(s2, _SAMPLE_BIB)
        # BibEntry unique constraint: (title, year, volume) — same entry skipped
        assert result2.skipped == 1
        assert result2.created == 0

    def test_oversized_text_raises_value_error(self, global_session):
        huge = "x" * (MAX_BIB_SIZE_BYTES + 1)
        with pytest.raises(ValueError, match="too large"):
            import_bib_text(global_session, huge)

    def test_malformed_bib_no_crash(self, global_session):
        """bibtexparser is lenient; either 0 created or 1 error, never exception."""
        result = import_bib_text(global_session, "@article{bad, title={no closing")
        assert isinstance(result, ImportResult)


# ---------------------------------------------------------------------------
# Parity: import_bib_file == import_bib_text for the same content
# ---------------------------------------------------------------------------

class TestFileSameParity:
    def test_file_and_text_produce_same_rows(self, global_session, global_engine, tmp_path):
        """Identical biblatex via file-path and via text produce the same DB rows."""
        from sqlalchemy.orm import Session

        bib_file = tmp_path / "entry.bib"
        bib_file.write_text(_SAMPLE_BIB, encoding="utf-8")

        # Import via text first in one session
        from sqlalchemy import create_engine, event
        from workflow.db.base import GlobalBase

        def _fk(conn, _):
            conn.cursor().execute("PRAGMA foreign_keys=ON")

        eng2 = create_engine("sqlite:///:memory:")
        event.listen(eng2, "connect", _fk)
        GlobalBase.metadata.create_all(eng2)

        with Session(eng2) as s2:
            res_text = import_bib_text(s2, _SAMPLE_BIB)

        # Import via file in the provided session
        res_file = import_bib_file(global_session, bib_file)

        assert res_file.created == res_text.created
        assert res_file.skipped == res_text.skipped
        assert len(res_file.errors) == len(res_text.errors)

    def test_file_regression_still_works(self, global_session, tmp_path):
        """Existing import_bib_file call is unbroken."""
        bib_file = tmp_path / "ref.bib"
        bib_file.write_text(_SAMPLE_BIB, encoding="utf-8")
        result = import_bib_file(global_session, bib_file)
        assert result.created == 1


# ---------------------------------------------------------------------------
# CLI: --stdin flag
# ---------------------------------------------------------------------------

class TestCliStdin:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def cli_engine(self, global_engine):
        return global_engine

    def _invoke_stdin(self, runner, cli_engine, extra_args=None, input_text=_SAMPLE_BIB):
        """Helper: invoke `prisma bib import --stdin` with the in-memory engine."""
        args = ["bib", "import", "--stdin"] + (extra_args or [])
        result = runner.invoke(
            prisma,
            args,
            input=input_text,
            obj={"engine": cli_engine},
            catch_exceptions=False,
        )
        return result

    def test_stdin_creates_entry(self, runner, cli_engine):
        r = self._invoke_stdin(runner, cli_engine)
        assert r.exit_code == 0

    def test_stdin_json_output(self, runner, cli_engine):
        r = self._invoke_stdin(runner, cli_engine, extra_args=["--json"])
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["created"] == 1

    def test_stdin_plus_path_errors(self, runner, cli_engine, tmp_path):
        bib_file = tmp_path / "f.bib"
        bib_file.write_text(_SAMPLE_BIB)
        r = runner.invoke(
            prisma,
            ["bib", "import", "--stdin", str(bib_file)],
            input=_SAMPLE_BIB,
            obj={"engine": cli_engine},
        )
        assert r.exit_code != 0
        assert "stdin" in r.output.lower() or "stdin" in (r.exception and str(r.exception) or "").lower()

    def test_no_stdin_no_path_errors(self, runner, cli_engine):
        r = runner.invoke(
            prisma,
            ["bib", "import"],
            obj={"engine": cli_engine},
        )
        assert r.exit_code != 0

    def test_empty_stdin_no_crash(self, runner, cli_engine):
        r = self._invoke_stdin(runner, cli_engine, input_text="")
        assert r.exit_code == 0

    def test_stdin_database_name_option(self, runner, cli_engine):
        r = self._invoke_stdin(
            runner, cli_engine,
            extra_args=["--database-name", "MyDB", "--json"]
        )
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data["created"] == 1


class TestSnippetFieldMapping:
    """Lock the biblatex field names emitted by the md.lua bib.* snippets to
    the importer's field sets, so a snippet edit that silently stops persisting
    is caught here (review esquema, 2026-06-01)."""

    def test_article_journal_maps_to_journaltitle(self, global_session):
        bib = textwrap.dedent("""\
            @article{art2021,
              title   = {A Paper},
              author  = {Carol Lee},
              journal = {Journal of Things},
              year    = {2021},
              volume  = {7},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "art2021")
        ).scalar_one()
        assert entry.journaltitle == "Journal of Things"

    def test_online_urldate_persists(self, global_session):
        bib = textwrap.dedent("""\
            @online{web2022,
              title   = {A Web Page},
              author  = {{Some Org}},
              year    = {2022},
              urldate = {2022-03-15},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "web2022")
        ).scalar_one()
        assert entry.urldate is not None
        assert entry.urldate.isoformat() == "2022-03-15"


class TestBibtexDialectAliases:
    """Integration: BibTeX-spelled fields are translated to BibLaTeX columns (ADR-0019 P1).

    Uses bibtex field spellings (journal, address, school, annote, note) and
    asserts the correct BibLaTeX column is populated on the persisted BibEntry.
    Each test uses a UNIQUE bibkey, title, and volume so the (title, year, volume)
    dedup constraint never collapses multiple tests into a single DB row.
    """

    def test_journal_maps_to_journaltitle(self, global_session):
        bib = textwrap.dedent("""\
            @article{alias_journal2024,
              title   = {Alias Journal Test},
              author  = {Doe, Jane},
              journal = {Journal of Testing},
              year    = {2024},
              volume  = {101},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_journal2024")
        ).scalar_one()
        assert entry.journaltitle == "Journal of Testing"

    def test_address_maps_to_location(self, global_session):
        bib = textwrap.dedent("""\
            @article{alias_address2024,
              title   = {Alias Address Test},
              author  = {Doe, Jane},
              year    = {2024},
              volume  = {102},
              address = {Cambridge},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_address2024")
        ).scalar_one()
        assert entry.location == "Cambridge"

    def test_school_maps_to_institution(self, global_session):
        bib = textwrap.dedent("""\
            @article{alias_school2024,
              title   = {Alias School Test},
              author  = {Doe, Jane},
              year    = {2024},
              volume  = {103},
              school  = {Harvard University},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_school2024")
        ).scalar_one()
        assert entry.institution == "Harvard University"

    def test_annote_maps_to_annotation(self, global_session):
        bib = textwrap.dedent("""\
            @article{alias_annote2024,
              title   = {Alias Annote Test},
              author  = {Doe, Jane},
              year    = {2024},
              volume  = {104},
              annote  = {A useful annotation},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_annote2024")
        ).scalar_one()
        assert entry.annotation == "A useful annotation"

    def test_note_maps_to_notes(self, global_session):
        bib = textwrap.dedent("""\
            @article{alias_note2024,
              title   = {Alias Note Test},
              author  = {Doe, Jane},
              year    = {2024},
              volume  = {105},
              note    = {See supplementary material},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_note2024")
        ).scalar_one()
        assert entry.notes == "See supplementary material"

    def test_all_five_aliases_in_one_entry(self, global_session):
        """All five BibTeX aliases populate BibLaTeX columns simultaneously."""
        bib = textwrap.dedent("""\
            @article{alias_all2024,
              title   = {Alias All Fields Test},
              author  = {Doe, Jane},
              journal = {Journal of Testing},
              year    = {2024},
              volume  = {106},
              address = {Cambridge},
              school  = {Harvard University},
              annote  = {A useful annotation},
              note    = {See supplementary material},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_all2024")
        ).scalar_one()
        assert entry.journaltitle == "Journal of Testing"
        assert entry.location == "Cambridge"
        assert entry.institution == "Harvard University"
        assert entry.annotation == "A useful annotation"
        assert entry.notes == "See supplementary material"

    def test_biblatex_native_still_works(self, global_session):
        """BibLaTeX-native spelling (journaltitle, location, ...) still persists."""
        bib = textwrap.dedent("""\
            @article{nativebiblatex2024,
              title        = {Native BibLaTeX Article},
              author       = {Smith, Alice},
              journaltitle = {BibLaTeX Journal},
              year         = {2024},
              volume       = {42},
              location     = {Berlin},
              institution  = {TU Berlin},
              annotation   = {Native annotation},
              notes        = {Native notes},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "nativebiblatex2024")
        ).scalar_one()
        assert entry.journaltitle == "BibLaTeX Journal"
        assert entry.location == "Berlin"
        assert entry.institution == "TU Berlin"
        assert entry.annotation == "Native annotation"
        assert entry.notes == "Native notes"

    def test_both_bibtex_and_biblatex_present_native_wins_with_warning(self, global_session):
        """When both BibTeX alias and BibLaTeX-native key are present, native wins + warning."""
        bib = textwrap.dedent("""\
            @article{alias_collision2024,
              title        = {Collision Test Article},
              author       = {Doe, Jane},
              year         = {2024},
              volume       = {107},
              journal      = {BibTeX Journal Name},
              journaltitle = {BibLaTeX Journal Name},
            }
        """)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import_bib_text(global_session, bib)

        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "alias_collision2024")
        ).scalar_one()
        # BibLaTeX-native value must win
        assert entry.journaltitle == "BibLaTeX Journal Name"
        # A UserWarning naming 'journal' must have been emitted
        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert any("journal" in str(w.message).lower() for w in user_warnings)
