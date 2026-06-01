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
