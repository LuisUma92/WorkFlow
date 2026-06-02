"""Tests for ADR-0019 Phase 2a — biblatex dialect columns.

Covers:
- BibEntry.date stored verbatim (EDTF range + single year)
- year/month derived from date when not explicitly set
- chapter and type persist on import
- Author name_prefix / name_suffix from von/jr particles
- Plain "First Last" leaves prefix/suffix None
- Migration 0012 idempotency
"""

from __future__ import annotations

import importlib
import textwrap

import pytest
from sqlalchemy import create_engine, inspect, select, text

from workflow.db.models.bibliography import Author, BibEntry
from workflow.prisma.importer import _extract_von, _split_authors, import_bib_text


# ---------------------------------------------------------------------------
# Importer: date field
# ---------------------------------------------------------------------------


class TestDateField:
    """BibEntry.date verbatim storage + year/month derivation."""

    def test_edtf_range_date_stored_verbatim(self, global_session):
        bib = textwrap.dedent("""\
            @book{rangetest,
              title = {Range Test},
              date  = {2010/2015},
              volume = {9},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "rangetest")
        ).scalar_one()
        assert entry.date == "2010/2015"

    def test_edtf_range_year_derived_from_first_component(self, global_session):
        bib = textwrap.dedent("""\
            @book{rangetest2,
              title = {Range Test 2},
              date  = {2010/2015},
              volume = {91},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "rangetest2")
        ).scalar_one()
        assert entry.year == 2010

    def test_edtf_range_with_month(self, global_session):
        """date={2010-03/2015} → year=2010, month='03', date='2010-03/2015'."""
        bib = textwrap.dedent("""\
            @book{monthrange,
              title = {Month Range},
              date  = {2010-03/2015},
              volume = {92},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "monthrange")
        ).scalar_one()
        assert entry.date == "2010-03/2015"
        assert entry.year == 2010
        assert entry.month == "03"

    def test_single_year_date(self, global_session):
        """date={2010} → date='2010', year=2010."""
        bib = textwrap.dedent("""\
            @book{singleyear,
              title = {Single Year},
              date  = {2010},
              volume = {93},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "singleyear")
        ).scalar_one()
        assert entry.date == "2010"
        assert entry.year == 2010

    def test_explicit_year_field_wins_over_date_derived(self, global_session):
        """Explicit year= field takes priority; date still stored verbatim."""
        bib = textwrap.dedent("""\
            @book{explicityear,
              title = {Explicit Year},
              year  = {1999},
              date  = {2010/2015},
              volume = {94},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "explicityear")
        ).scalar_one()
        # year from explicit field; date verbatim
        assert entry.year == 1999
        assert entry.date == "2010/2015"

    def test_no_date_field_leaves_date_none(self, global_session):
        """Entries with only year= should have date=None."""
        bib = textwrap.dedent("""\
            @book{nodatefield,
              title = {No Date Field},
              year  = {2020},
              volume = {95},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "nodatefield")
        ).scalar_one()
        assert entry.date is None
        assert entry.year == 2020


# ---------------------------------------------------------------------------
# Importer: chapter and type
# ---------------------------------------------------------------------------


class TestChapterAndType:
    def test_chapter_persists(self, global_session):
        bib = textwrap.dedent("""\
            @incollection{chaptest,
              title   = {Chapter Test},
              chapter = {5},
              year    = {2021},
              volume  = {10},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "chaptest")
        ).scalar_one()
        assert entry.chapter == "5"

    def test_type_persists(self, global_session):
        bib = textwrap.dedent("""\
            @report{typetest,
              title  = {Type Test},
              type   = {Technical Report},
              year   = {2022},
              volume = {11},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "typetest")
        ).scalar_one()
        assert entry.type == "Technical Report"

    def test_chapter_and_type_together(self, global_session):
        bib = textwrap.dedent("""\
            @incollection{chaptype,
              title   = {Chap and Type},
              chapter = {3},
              type    = {section},
              year    = {2023},
              volume  = {12},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "chaptype")
        ).scalar_one()
        assert entry.chapter == "3"
        assert entry.type == "section"


# ---------------------------------------------------------------------------
# Author von/jr particles
# ---------------------------------------------------------------------------


class TestSplitAuthors:
    def test_plain_first_last(self):
        result = _split_authors("John Smith")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "John"
        assert last == "Smith"
        assert prefix is None
        assert suffix is None

    def test_last_comma_first(self):
        result = _split_authors("Smith, John")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "John"
        assert last == "Smith"
        assert prefix is None
        assert suffix is None

    def test_von_particle_in_last_comma_first(self):
        """'van Beethoven, Ludwig' → prefix='van'."""
        result = _split_authors("van Beethoven, Ludwig")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "Ludwig"
        assert last == "Beethoven"
        assert prefix == "van"
        assert suffix is None

    def test_jr_suffix_three_part(self):
        """'Smith, Jr, John' → suffix='Jr'."""
        result = _split_authors("Smith, Jr, John")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "John"
        assert last == "Smith"
        assert suffix == "Jr"
        assert prefix is None

    def test_von_and_jr_combined(self):
        """'von Smith, Jr, John' → prefix='von', suffix='Jr'."""
        result = _split_authors("von Smith, Jr, John")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "John"
        assert last == "Smith"
        assert prefix == "von"
        assert suffix == "Jr"

    def test_multiple_authors(self):
        result = _split_authors("Smith, John and Jones, Alice")
        assert len(result) == 2
        assert result[0][1] == "Smith"
        assert result[1][1] == "Jones"

    def test_corporate_name(self):
        result = _split_authors("{IEEE Standards Association}")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == ""
        assert "IEEE" in last
        assert prefix is None
        assert suffix is None


class TestExtractVon:
    def test_no_prefix(self):
        last, prefix = _extract_von("Smith")
        assert last == "Smith"
        assert prefix == ""

    def test_single_von(self):
        last, prefix = _extract_von("von Smith")
        assert last == "Smith"
        assert prefix == "von"

    def test_multi_word_von(self):
        last, prefix = _extract_von("von der Heide")
        assert last == "Heide"
        assert prefix == "von der"

    def test_uppercase_not_treated_as_von(self):
        last, prefix = _extract_von("Van Smith")
        # "Van" starts with uppercase — not a von particle
        assert last == "Van Smith"
        assert prefix == ""


# ---------------------------------------------------------------------------
# Author DB: prefix/suffix stored via import
# ---------------------------------------------------------------------------


class TestAuthorPrefixSuffixDB:
    def test_von_prefix_stored_on_author(self, global_session):
        bib = textwrap.dedent("""\
            @book{vontest,
              title  = {Von Test},
              author = {van Beethoven, Ludwig},
              year   = {1820},
              volume = {20},
            }
        """)
        import_bib_text(global_session, bib)
        author = global_session.execute(
            select(Author).where(Author.last_name == "Beethoven")
        ).scalar_one()
        assert author.name_prefix == "van"
        assert author.name_suffix is None

    def test_jr_suffix_stored_on_author(self, global_session):
        bib = textwrap.dedent("""\
            @book{jrtest,
              title  = {Jr Test},
              author = {Smith, Jr, John},
              year   = {2000},
              volume = {21},
            }
        """)
        import_bib_text(global_session, bib)
        author = global_session.execute(
            select(Author).where(Author.last_name == "Smith")
        ).scalar_one()
        assert author.name_suffix == "Jr"

    def test_plain_author_no_prefix_suffix(self, global_session):
        bib = textwrap.dedent("""\
            @book{plainauthor,
              title  = {Plain Author},
              author = {Alice Johnson},
              year   = {2001},
              volume = {22},
            }
        """)
        import_bib_text(global_session, bib)
        author = global_session.execute(
            select(Author).where(Author.last_name == "Johnson")
        ).scalar_one()
        assert author.name_prefix is None
        assert author.name_suffix is None


# ---------------------------------------------------------------------------
# Migration 0012 idempotency
# ---------------------------------------------------------------------------


def _load_migration():
    return importlib.import_module(
        "workflow.db.migrations.global.0012_bib_dialect_columns"
    )


def _col_names(engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


@pytest.fixture
def pre_0012_engine():
    """Minimal in-memory DB resembling pre-0012 schema (no dialect columns)."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE bib_entry (
                id          INTEGER PRIMARY KEY,
                title       VARCHAR(500),
                year        SMALLINT,
                month       VARCHAR(10),
                volume      VARCHAR(20)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE author (
                id          INTEGER PRIMARY KEY,
                first_name  VARCHAR(80),
                last_name   VARCHAR(200)
            )
            """
        )
        # Seed a pre-existing row to test backfill
        conn.exec_driver_sql(
            "INSERT INTO bib_entry (id, title, year, month, volume) "
            "VALUES (1, 'Old Book', 2005, '03', 'V1')"
        )
        conn.exec_driver_sql(
            "INSERT INTO bib_entry (id, title, year, volume) "
            "VALUES (2, 'Old Book No Month', 2006, 'V2')"
        )
    return eng


def test_migration_adds_columns_bib_entry(pre_0012_engine):
    with pre_0012_engine.begin() as conn:
        _load_migration().upgrade(conn)
    cols = _col_names(pre_0012_engine, "bib_entry")
    assert "date" in cols
    assert "chapter" in cols
    assert "type" in cols


def test_migration_adds_columns_author(pre_0012_engine):
    with pre_0012_engine.begin() as conn:
        _load_migration().upgrade(conn)
    cols = _col_names(pre_0012_engine, "author")
    assert "name_prefix" in cols
    assert "name_suffix" in cols


def test_migration_backfills_date_with_month(pre_0012_engine):
    with pre_0012_engine.begin() as conn:
        _load_migration().upgrade(conn)
    with pre_0012_engine.connect() as conn:
        row = conn.execute(
            text("SELECT date FROM bib_entry WHERE id=1")
        ).one()
    assert row[0] == "2005-03"


def test_migration_backfills_date_without_month(pre_0012_engine):
    with pre_0012_engine.begin() as conn:
        _load_migration().upgrade(conn)
    with pre_0012_engine.connect() as conn:
        row = conn.execute(
            text("SELECT date FROM bib_entry WHERE id=2")
        ).one()
    assert row[0] == "2006"


def test_migration_idempotent(pre_0012_engine):
    """Applying migration twice raises no error and leaves columns intact."""
    mod = _load_migration()
    with pre_0012_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_0012_engine.begin() as conn:
        mod.upgrade(conn)
    cols = _col_names(pre_0012_engine, "bib_entry")
    assert "date" in cols
    assert "chapter" in cols
    assert "type" in cols
    author_cols = _col_names(pre_0012_engine, "author")
    assert "name_prefix" in author_cols
    assert "name_suffix" in author_cols


def test_migration_metadata():
    mod = _load_migration()
    assert mod.revision == "0012_bib_dialect_columns"
    assert mod.base == "global"


# ---------------------------------------------------------------------------
# Fix 1 — natural-order von particle extraction
# ---------------------------------------------------------------------------


class TestNaturalOrderVon:
    """'First von Last' natural-order form must extract the von particle."""

    def test_natural_order_von_particle(self):
        """'Ludwig van Beethoven' → first='Ludwig', prefix='van', last='Beethoven'."""
        result = _split_authors("Ludwig van Beethoven")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "Ludwig"
        assert last == "Beethoven"
        assert prefix == "van"
        assert suffix is None

    def test_natural_order_no_particle(self):
        """'John Smith' (no particle) → prefix=None; regression guard."""
        result = _split_authors("John Smith")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "John"
        assert last == "Smith"
        assert prefix is None
        assert suffix is None

    def test_natural_order_capitalized_last_no_particle(self):
        """Capitalized multi-word last name without a particle stays intact."""
        result = _split_authors("Jean-Paul Sartre")
        assert len(result) == 1
        first, last, prefix, suffix = result[0]
        assert first == "Jean-Paul"
        assert last == "Sartre"
        assert prefix is None
        assert suffix is None


# ---------------------------------------------------------------------------
# Fix 2 — dual-write: verbatim date + derived year/month + publication_date
# ---------------------------------------------------------------------------


class TestDualWriteDate:
    """date={2010/2015} must populate BOTH the verbatim date column AND derived fields."""

    def test_range_date_dual_write(self, global_session):
        """date={2010/2015} → date='2010/2015', year=2010, publication_date non-null."""
        bib = textwrap.dedent("""\
            @book{dualwrite1,
              title  = {Dual Write Test},
              date   = {2010/2015},
              volume = {30},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "dualwrite1")
        ).scalar_one()
        # verbatim literal preserved
        assert entry.date == "2010/2015"
        # year derived from first EDTF component
        assert entry.year == 2010
        # publication_date (datetime) populated and its year matches
        assert entry.publication_date is not None
        assert entry.publication_date.year == 2010


# ---------------------------------------------------------------------------
# Fix 3 — migration: non-numeric month backfill + idempotency
# ---------------------------------------------------------------------------


@pytest.fixture
def pre_0012_non_numeric_month_engine():
    """DB with a row whose month is a non-numeric string (e.g. 'Jan')."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE bib_entry (
                id     INTEGER PRIMARY KEY,
                title  VARCHAR(500),
                year   SMALLINT,
                month  VARCHAR(10),
                volume VARCHAR(20)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE author (
                id         INTEGER PRIMARY KEY,
                first_name VARCHAR(80),
                last_name  VARCHAR(200)
            )
            """
        )
        # row with non-numeric month — must NOT produce "2024-Jan"
        conn.exec_driver_sql(
            "INSERT INTO bib_entry (id, title, year, month, volume) "
            "VALUES (1, 'Old Book Jan', 2024, 'Jan', 'V10')"
        )
        # row with numeric month — must produce "2024-03"
        conn.exec_driver_sql(
            "INSERT INTO bib_entry (id, title, year, month, volume) "
            "VALUES (2, 'Old Book Mar', 2024, '03', 'V11')"
        )
        # row with no month — must produce "2025"
        conn.exec_driver_sql(
            "INSERT INTO bib_entry (id, title, year, volume) "
            "VALUES (3, 'No Month', 2025, 'V12')"
        )
    return eng


def test_migration_backfill_non_numeric_month_produces_year_only(
    pre_0012_non_numeric_month_engine,
):
    """Non-numeric month (e.g. 'Jan') must NOT be appended; result must be 'YYYY'."""
    with pre_0012_non_numeric_month_engine.begin() as conn:
        _load_migration().upgrade(conn)
    with pre_0012_non_numeric_month_engine.connect() as conn:
        row = conn.execute(text("SELECT date FROM bib_entry WHERE id=1")).one()
    assert row[0] == "2024", f"Expected '2024', got {row[0]!r}"


def test_migration_backfill_numeric_month_produces_iso(
    pre_0012_non_numeric_month_engine,
):
    """Numeric month '03' must produce ISO literal '2024-03'."""
    with pre_0012_non_numeric_month_engine.begin() as conn:
        _load_migration().upgrade(conn)
    with pre_0012_non_numeric_month_engine.connect() as conn:
        row = conn.execute(text("SELECT date FROM bib_entry WHERE id=2")).one()
    assert row[0] == "2024-03", f"Expected '2024-03', got {row[0]!r}"


def test_migration_backfill_no_month_produces_year_only(
    pre_0012_non_numeric_month_engine,
):
    """Row with no month must produce year-only literal '2025'."""
    with pre_0012_non_numeric_month_engine.begin() as conn:
        _load_migration().upgrade(conn)
    with pre_0012_non_numeric_month_engine.connect() as conn:
        row = conn.execute(text("SELECT date FROM bib_entry WHERE id=3")).one()
    assert row[0] == "2025", f"Expected '2025', got {row[0]!r}"


def test_migration_backfill_idempotent_on_non_numeric(
    pre_0012_non_numeric_month_engine,
):
    """Re-running migration leaves backfilled dates unchanged (idempotent)."""
    mod = _load_migration()
    with pre_0012_non_numeric_month_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_0012_non_numeric_month_engine.begin() as conn:
        mod.upgrade(conn)
    with pre_0012_non_numeric_month_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, date FROM bib_entry ORDER BY id")
        ).fetchall()
    assert rows[0][1] == "2024"
    assert rows[1][1] == "2024-03"
    assert rows[2][1] == "2025"


# ---------------------------------------------------------------------------
# Fix 4 — open / reverse EDTF range edge cases
# ---------------------------------------------------------------------------


class TestEdtfEdgeCases:
    def test_open_end_range(self, global_session):
        """date={2010/} (open end) → year=2010, date stored verbatim."""
        bib = textwrap.dedent("""\
            @book{openend,
              title  = {Open End Range},
              date   = {2010/},
              volume = {40},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "openend")
        ).scalar_one()
        assert entry.date == "2010/"
        assert entry.year == 2010

    def test_open_start_range_does_not_crash(self, global_session):
        """date={/2015} (open start) → does not crash; date stored verbatim; year is None."""
        bib = textwrap.dedent("""\
            @book{openstart,
              title  = {Open Start Range},
              date   = {/2015},
              volume = {41},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.bibkey == "openstart")
        ).scalar_one()
        assert entry.date == "/2015"
        # first component before '/' is empty → year cannot be parsed → None
        assert entry.year is None
