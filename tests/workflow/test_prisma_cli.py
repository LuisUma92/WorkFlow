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
    BibUrl,
    ReferencedDatabase,
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


# ── P1: bib search ──────────────────────────────────────────────────────


class TestPrismaBibSearch:
    def test_search_by_title(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["bib", "search", "--title", "machine learning"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Machine learning in education" in result.output
        assert "Natural language" not in result.output

    def test_search_by_author(self, runner, seeded_engine):
        result = _invoke(
            runner, prisma, ["bib", "search", "--author", "Smith"], seeded_engine
        )
        assert result.exit_code == 0
        assert "Machine learning" in result.output
        assert "Deep learning" not in result.output

    def test_search_by_year(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["bib", "search", "--title", "learning", "--year", "2024"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Deep learning" in result.output
        assert "Machine learning in education" not in result.output

    def test_search_no_results(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["bib", "search", "--title", "nonexistent topic"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "No bibliography entries found" in result.output

    def test_search_json(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["bib", "search", "--title", "learning", "--json"],
            seeded_engine,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) >= 2
        titles = [d["title"] for d in data]
        assert any("learning" in t.lower() for t in titles)

    def test_search_requires_at_least_one_filter(self, runner, seeded_engine):
        result = _invoke(runner, prisma, ["bib", "search"], seeded_engine)
        assert result.exit_code != 0


# ── P1: keyword add ─────────────────────────────────────────────────────


class TestPrismaKeywordAdd:
    def test_add_keyword(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["keyword", "add", "--text", "neural networks"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Created keyword" in result.output

    def test_add_keyword_shows_in_list(self, runner, seeded_engine):
        _invoke(
            runner,
            prisma,
            ["keyword", "add", "--text", "quantum computing"],
            seeded_engine,
        )
        result = _invoke(runner, prisma, ["keyword", "list", "--json"], seeded_engine)
        data = json.loads(result.output)
        kw_texts = [d["keyword_list"] for d in data]
        assert "quantum computing" in kw_texts

    def test_add_keyword_duplicate_fails(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["keyword", "add", "--text", "machine learning education"],
            seeded_engine,
        )
        assert result.exit_code != 0


# ── P1: tag list/add ────────────────────────────────────────────────────


class TestPrismaTagList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, prisma, ["tag", "list"], engine)
        assert result.exit_code == 0
        assert "No tags found" in result.output

    def test_list_json_empty(self, runner, engine):
        result = _invoke(runner, prisma, ["tag", "list", "--json"], engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestPrismaTagAdd:
    def test_add_tag(self, runner, seeded_engine):
        result = _invoke(
            runner, prisma, ["tag", "add", "--text", "methodology"], seeded_engine
        )
        assert result.exit_code == 0
        assert "Created tag" in result.output

    def test_add_tag_shows_in_list(self, runner, seeded_engine):
        _invoke(runner, prisma, ["tag", "add", "--text", "review-paper"], seeded_engine)
        result = _invoke(runner, prisma, ["tag", "list", "--json"], seeded_engine)
        data = json.loads(result.output)
        tags = [d["tag"] for d in data]
        assert "review-paper" in tags

    def test_add_tag_duplicate_fails(self, runner, seeded_engine):
        _invoke(runner, prisma, ["tag", "add", "--text", "dup-tag"], seeded_engine)
        result = _invoke(
            runner, prisma, ["tag", "add", "--text", "dup-tag"], seeded_engine
        )
        assert result.exit_code != 0


# ── P1: rationale list/add ───────────────────────────────────────────────


class TestPrismaRationaleList:
    def test_list_empty(self, runner, engine):
        result = _invoke(runner, prisma, ["rationale", "list"], engine)
        assert result.exit_code == 0
        assert "No rationales found" in result.output


class TestPrismaRationaleAdd:
    def test_add_rationale(self, runner, seeded_engine):
        result = _invoke(
            runner,
            prisma,
            ["rationale", "add", "--text", "Not peer-reviewed"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "Created rationale" in result.output

    def test_add_rationale_duplicate_fails(self, runner, seeded_engine):
        _invoke(
            runner,
            prisma,
            ["rationale", "add", "--text", "Same rationale"],
            seeded_engine,
        )
        result = _invoke(
            runner,
            prisma,
            ["rationale", "add", "--text", "Same rationale"],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_add_rationale_shows_in_list(self, runner, seeded_engine):
        _invoke(
            runner,
            prisma,
            ["rationale", "add", "--text", "Duplicate study"],
            seeded_engine,
        )
        result = _invoke(runner, prisma, ["rationale", "list", "--json"], seeded_engine)
        data = json.loads(result.output)
        args = [d["rationale_argument"] for d in data]
        assert "Duplicate study" in args


# ── P1: review screen ───────────────────────────────────────────────────


class TestPrismaReviewScreen:
    def test_screen_include(self, runner, seeded_engine):
        """Screen an article as included for a keyword."""
        bib_id = _find_bib_id(runner, seeded_engine, "Natural language")
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "screen", bib_id, "--keyword-id", kw_id, "--include"],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "included" in result.output.lower()

    def test_screen_exclude_with_rationale(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw2_id = str(json.loads(kw_result.output)[1]["id"])

        # b3 (NLP) has no review for kw2
        bib_id_nlp = _find_bib_id(runner, seeded_engine, "Natural language")

        result = _invoke(
            runner,
            prisma,
            [
                "review",
                "screen",
                bib_id_nlp,
                "--keyword-id",
                kw2_id,
                "--exclude",
                "--rationale",
                "Off topic for image recognition",
            ],
            seeded_engine,
        )
        assert result.exit_code == 0
        assert "excluded" in result.output.lower()

    def test_screen_updates_review_list(self, runner, seeded_engine):
        """After screening, the record appears in review list."""
        bib_id = _find_bib_id(runner, seeded_engine, "Natural language")
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        # kw1 already has a pending review for b3 — screen it
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        _invoke(
            runner,
            prisma,
            ["review", "screen", bib_id, "--keyword-id", kw_id, "--include"],
            seeded_engine,
        )

        result = _invoke(
            runner,
            prisma,
            ["review", "list", "--keyword-id", kw_id, "--status", "included", "--json"],
            seeded_engine,
        )
        data = json.loads(result.output)
        titles = [d["title"] for d in data]
        assert "Natural language processing overview" in titles

    def test_screen_nonexistent_article(self, runner, seeded_engine):
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "screen", "9999", "--keyword-id", kw_id, "--include"],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_screen_nonexistent_keyword(self, runner, seeded_engine):
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")
        result = _invoke(
            runner,
            prisma,
            ["review", "screen", bib_id, "--keyword-id", "9999", "--include"],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_screen_requires_include_or_exclude(self, runner, seeded_engine):
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "screen", bib_id, "--keyword-id", kw_id],
            seeded_engine,
        )
        assert result.exit_code != 0

    def test_screen_already_decided_fails(self, runner, seeded_engine):
        """Screening an already-included/excluded article raises error."""
        # b1 is already included for kw1 in seed data
        bib_id = _find_bib_id(runner, seeded_engine, "Machine learning")
        kw_result = _invoke(
            runner, prisma, ["keyword", "list", "--json"], seeded_engine
        )
        kw_id = str(json.loads(kw_result.output)[0]["id"])

        result = _invoke(
            runner,
            prisma,
            ["review", "screen", bib_id, "--keyword-id", kw_id, "--exclude"],
            seeded_engine,
        )
        assert result.exit_code != 0
        assert "already screened" in result.output.lower()


# ── prisma bib import ───────────────────────────────────────────────────

SAMPLE_BIB = r"""@article{smith2023ml,
  title = {Machine learning in education},
  author = {Smith, John and Doe, Jane},
  journal = {J. Educational Tech},
  year = {2023},
  volume = {10},
  doi = {10.1000/abc},
}

@article{jones2024dl,
  title = {Deep learning for vision},
  author = {Jones, Bob},
  journal = {Neural Computing},
  year = {2024},
  volume = {5},
}
"""


def _write_bib(tmp_path, content, name="sample.bib"):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


class TestPrismaBibImport:
    def test_import_creates_entries(self, runner, engine, tmp_path):
        path = _write_bib(tmp_path, SAMPLE_BIB)
        result = _invoke(runner, prisma, ["bib", "import", path], engine)
        assert result.exit_code == 0, result.output
        assert "created" in result.output.lower()
        with Session(engine) as s:
            assert s.query(BibEntry).count() == 2

    def test_import_dedup_skips_on_reimport(self, runner, engine, tmp_path):
        path = _write_bib(tmp_path, SAMPLE_BIB)
        _invoke(runner, prisma, ["bib", "import", path], engine)
        result = _invoke(runner, prisma, ["bib", "import", path], engine)
        assert result.exit_code == 0
        with Session(engine) as s:
            assert s.query(BibEntry).count() == 2
        assert "skipped" in result.output.lower()

    def test_import_author_comma_format(self, runner, engine, tmp_path):
        path = _write_bib(tmp_path, SAMPLE_BIB)
        _invoke(runner, prisma, ["bib", "import", path], engine)
        with Session(engine) as s:
            names = {(a.first_name, a.last_name) for a in s.query(Author).all()}
        assert ("John", "Smith") in names
        assert ("Jane", "Doe") in names

    def test_import_author_space_format(self, runner, engine, tmp_path):
        bib = r"""@article{x2020,
  title = {T},
  author = {John Smith},
  year = {2020},
}
"""
        path = _write_bib(tmp_path, bib)
        _invoke(runner, prisma, ["bib", "import", path], engine)
        with Session(engine) as s:
            names = {(a.first_name, a.last_name) for a in s.query(Author).all()}
        assert ("John", "Smith") in names

    def test_import_author_corporate_braces(self, runner, engine, tmp_path):
        bib = r"""@book{acme2020,
  title = {Handbook},
  author = {{Acme Corporation}},
  year = {2020},
}
"""
        path = _write_bib(tmp_path, bib)
        _invoke(runner, prisma, ["bib", "import", path], engine)
        with Session(engine) as s:
            names = {(a.first_name, a.last_name) for a in s.query(Author).all()}
        assert ("", "Acme Corporation") in names

    def test_import_multiple_author_types(self, runner, engine, tmp_path):
        bib = r"""@book{ed2021,
  title = {Collection},
  author = {Smith, Alice},
  editor = {Jones, Bob},
  year = {2021},
}
"""
        path = _write_bib(tmp_path, bib)
        _invoke(runner, prisma, ["bib", "import", path], engine)
        with Session(engine) as s:
            links = s.query(BibAuthor).all()
            types = {link.author_type.type_of_author for link in links}
        assert "author" in types
        assert "editor" in types

    def test_import_missing_year(self, runner, engine, tmp_path):
        bib = r"""@misc{noyear,
  title = {Something},
  author = {Roe, Richard},
}
"""
        path = _write_bib(tmp_path, bib)
        result = _invoke(runner, prisma, ["bib", "import", path], engine)
        assert result.exit_code == 0
        with Session(engine) as s:
            e = s.query(BibEntry).first()
            assert e is not None
            assert e.year is None

    def test_import_empty_file(self, runner, engine, tmp_path):
        path = _write_bib(tmp_path, "")
        result = _invoke(runner, prisma, ["bib", "import", path], engine)
        assert result.exit_code == 0
        with Session(engine) as s:
            assert s.query(BibEntry).count() == 0

    def test_import_verbose_flag(self, runner, engine, tmp_path):
        path = _write_bib(tmp_path, SAMPLE_BIB)
        result = _invoke(runner, prisma, ["bib", "import", path, "--verbose"], engine)
        assert result.exit_code == 0
        assert "smith2023ml" in result.output
        assert "jones2024dl" in result.output

    def test_import_json_flag(self, runner, engine, tmp_path):
        path = _write_bib(tmp_path, SAMPLE_BIB)
        result = _invoke(runner, prisma, ["bib", "import", path, "--json"], engine)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] == 2
        assert data["skipped"] == 0
        assert isinstance(data["errors"], list)

    def test_import_url_creates_bib_url(self, runner, engine, tmp_path):
        bib = r"""@article{url2022,
  title = {With URL},
  author = {Noe, Nora},
  year = {2022},
  url = {https://example.com/paper},
}
"""
        path = _write_bib(tmp_path, bib)
        _invoke(
            runner,
            prisma,
            ["bib", "import", path, "--database-name", "PubMed"],
            engine,
        )
        with Session(engine) as s:
            urls = s.query(BibUrl).all()
            assert len(urls) == 1
            assert urls[0].url_string == "https://example.com/paper"
            dbs = s.query(ReferencedDatabase).all()
            assert any(d.name == "PubMed" for d in dbs)

    def test_import_nonexistent_file(self, runner, engine):
        result = _invoke(
            runner, prisma, ["bib", "import", "/nonexistent/file.bib"], engine
        )
        assert result.exit_code != 0
