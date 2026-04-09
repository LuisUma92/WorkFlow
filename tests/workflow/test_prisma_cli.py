"""Tests for PRISMA systematic review CLI (prisma bib, keyword, review)."""

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.bibliography import (
    Author,
    BibAuthor,
    AuthorType,
    BibEntry,
    BibKeyword,
    ReviewRecord,
)
from workflow.prisma.cli import prisma


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture
def seeded_engine(engine):
    """Engine with bib entries, keywords, reviews, and authors seeded."""
    with Session(engine) as session:
        # Author type
        at = AuthorType(type_of_author="author")
        session.add(at)
        session.flush()

        # Authors
        a1 = Author(first_name="Alice", last_name="Smith")
        a2 = Author(first_name="Bob", last_name="Jones")
        session.add_all([a1, a2])
        session.flush()

        # Bib entries
        b1 = BibEntry(
            title="Machine learning in education",
            year=2023,
            entry_type="article",
            bibkey="smith2023ml",
            journaltitle="J. Educational Tech",
            abstract_text="A systematic review of ML in education.",
        )
        b2 = BibEntry(
            title="Deep learning for image recognition",
            year=2024,
            entry_type="article",
            bibkey="jones2024dl",
            journaltitle="Neural Computing",
            abstract_text="Survey of DL methods for image tasks.",
        )
        b3 = BibEntry(
            title="Natural language processing overview",
            year=2022,
            entry_type="inproceedings",
            bibkey="doe2022nlp",
        )
        session.add_all([b1, b2, b3])
        session.flush()

        # Author links
        session.add(
            BibAuthor(
                bib_entry_id=b1.id,
                author_id=a1.id,
                author_type_id=at.id,
                first_author=True,
            )
        )
        session.add(
            BibAuthor(
                bib_entry_id=b2.id,
                author_id=a2.id,
                author_type_id=at.id,
                first_author=True,
            )
        )
        session.flush()

        # Keywords
        kw1 = BibKeyword(keyword_list="machine learning education")
        kw2 = BibKeyword(keyword_list="deep learning images")
        session.add_all([kw1, kw2])
        session.flush()

        # Review records
        r1 = ReviewRecord(
            keyword_id=kw1.id,
            bib_entry_id=b1.id,
            retrieved=1,
            included=1,
        )
        r2 = ReviewRecord(
            keyword_id=kw1.id,
            bib_entry_id=b2.id,
            retrieved=1,
            included=0,
            include_rationale="Not about education",
        )
        r3 = ReviewRecord(
            keyword_id=kw2.id,
            bib_entry_id=b2.id,
            retrieved=1,
            included=1,
        )
        # Pending review (included=None)
        r4 = ReviewRecord(
            keyword_id=kw1.id,
            bib_entry_id=b3.id,
            retrieved=1,
            included=None,
        )
        session.add_all([r1, r2, r3, r4])
        session.commit()
    return engine


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, cmd, args, engine):
    return runner.invoke(cmd, args, obj={"engine": engine}, catch_exceptions=False)


# ── prisma bib list ─────────────────────────────────────────────────────


class TestPrismaBibList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, prisma, ["bib", "list"], engine)
        assert result.exit_code == 0
        assert "No bibliography entries found" in result.output

    def test_list_shows_entries(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["bib", "list"], seeded_engine)
        assert result.exit_code == 0
        assert "Machine learning in education" in result.output
        assert "Deep learning for image recognition" in result.output

    def test_list_filter_by_year(self, runner, seeded_engine):
        result = _invoke(
            runner, prisma, ["bib", "list", "--year", "2023"], seeded_engine
        )
        assert result.exit_code == 0
        assert "Machine learning in education" in result.output
        assert "Deep learning" not in result.output

    def test_list_filter_by_type(self, runner, seeded_engine):
        result = _invoke(
            runner, prisma, ["bib", "list", "--type", "inproceedings"], seeded_engine
        )
        assert result.exit_code == 0
        assert "Natural language processing" in result.output
        assert "Machine learning" not in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["bib", "list", "--json"], seeded_engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert all("title" in d for d in data)

    def test_list_json_includes_authors(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["bib", "list", "--json"], seeded_engine)
        data = json.loads(result.output)
        ml_entry = [d for d in data if "Machine learning" in d["title"]][0]
        assert "authors" in ml_entry
        assert len(ml_entry["authors"]) == 1
        assert ml_entry["authors"][0]["last_name"] == "Smith"


# ── prisma bib show ─────────────────────────────────────────────────────


class TestPrismaBibShow:
    def test_show_existing(self, runner, seeded_engine):
        # Get id first
        result = _invoke(runner, prisma, ["bib", "list", "--json"], seeded_engine)
        bib_id = str(json.loads(result.output)[0]["id"])

        result = _invoke(runner, prisma, ["bib", "show", bib_id], seeded_engine)
        assert result.exit_code == 0

    def test_show_json(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["bib", "list", "--json"], seeded_engine)
        bib_id = str(json.loads(result.output)[0]["id"])

        result = _invoke(
            runner, prisma, ["bib", "show", bib_id, "--json"], seeded_engine
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "title" in data
        assert "abstract_text" in data
        assert "authors" in data

    def test_show_nonexistent(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["bib", "show", "9999"], seeded_engine)
        assert result.exit_code != 0


# ── prisma keyword list ──────────────────────────────────────────────────


class TestPrismaKeywordList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, prisma, ["keyword", "list"], engine)
        assert result.exit_code == 0
        assert "No keywords found" in result.output

    def test_list_shows_keywords(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["keyword", "list"], seeded_engine)
        assert result.exit_code == 0
        assert "machine learning education" in result.output

    def test_list_json(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["keyword", "list", "--json"], seeded_engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        kw_texts = [d["keyword_list"] for d in data]
        assert "machine learning education" in kw_texts


# ── prisma review list ───────────────────────────────────────────────────


class TestPrismaReviewList:
    def test_list_requires_keyword(self, runner, seeded_engine):
        """Review list requires --keyword-id."""
        result = _invoke(runner, prisma, ["review", "list"], seeded_engine)
        assert result.exit_code != 0

    def test_list_by_keyword(self, runner, seeded_engine):
        # Get keyword id
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner, prisma, ["review", "list", "--keyword-id", kw_id], seeded_engine
        )
        assert result.exit_code == 0
        assert "Machine learning in education" in result.output

    def test_list_filter_included(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--status", "included"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Machine learning in education" in result.output
        assert "Deep learning" not in result.output

    def test_list_filter_excluded(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--status", "excluded"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Deep learning" in result.output
        assert "Machine learning in education" not in result.output

    def test_list_json(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert all("title" in d for d in data)
        assert all("included" in d for d in data)

    def test_list_json_includes_rationale(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--json"],
            seeded_engine,
        )
        data = json.loads(result.output)
        excluded = [d for d in data if d["included"] == 0][0]
        assert excluded["include_rationale"] == "Not about education"

    def test_list_filter_pending(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--status", "pending"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Natural language processing" in result.output
        assert "Machine learning" not in result.output

    def test_list_nonexistent_keyword(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", "9999"],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_list_empty_result(self, runner, seeded_engine):
        """Keyword 2 has only 1 record (included); excluded filter → empty."""
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[1]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--status", "excluded"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "No review records found" in result.output


def _find_bib_id(runner, seeded_engine, title_substr):
    """Helper to find a bib entry id by title substring."""
    result = _invoke(runner, prisma, ["bib", "list", "--json"], seeded_engine)
    data = json.loads(result.output)
    entry = [d for d in data if title_substr in d["title"]][0]
    return str(entry["id"])


class TestPrismaBibShowTable:
    """Verify table output fields for bib show."""

    def test_show_table_has_title_and_year(self, runner, seeded_engine):
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")

        result = _invoke(runner, prisma, ["bib", "show", bib_id], seeded_engine)
        assert result.exit_code == 0
        assert "Machine learning in education" in result.output
        assert "2023" in result.output

    def test_show_table_has_journal(self, runner, seeded_engine):
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")

        result = _invoke(runner, prisma, ["bib", "show", bib_id], seeded_engine)
        assert "J. Educational Tech" in result.output

    def test_show_table_has_authors(self, runner, seeded_engine):
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")

        result = _invoke(runner, prisma, ["bib", "show", bib_id], seeded_engine)
        assert "Smith" in result.output
        assert "Alice" in result.output

    def test_show_table_has_abstract(self, runner, seeded_engine):
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")

        result = _invoke(runner, prisma, ["bib", "show", bib_id], seeded_engine)
        assert "systematic review of ML" in result.output
