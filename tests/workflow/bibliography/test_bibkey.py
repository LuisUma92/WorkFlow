"""Unit tests for workflow.bibliography.bibkey — calculate_bibkey.

TDD: RED → GREEN → REFACTOR.
Covers every locked rule from ADR-0019 Phase 1.
"""

from __future__ import annotations

from workflow.bibliography.bibkey import calculate_bibkey


# ---------------------------------------------------------------------------
# Book form — basic
# ---------------------------------------------------------------------------

class TestBookForm:
    def test_book_with_volume(self):
        result = calculate_bibkey(surname="Knuth", year=1997, volume="3",
                                  edition=3, entry_type="book")
        assert result == "knuth1997V03E03"

    def test_book_without_volume(self):
        result = calculate_bibkey(surname="Goldstein", year=2001, volume=None,
                                  edition=3, entry_type="book")
        assert result == "goldstein2001E03"

    def test_book_missing_edition_defaults_to_e01(self):
        result = calculate_bibkey(surname="Smith", year=2020, volume=None,
                                  edition=None, entry_type="book")
        assert result == "smith2020E01"

    def test_book_with_volume_and_default_edition(self):
        result = calculate_bibkey(surname="Jones", year=2005, volume="2",
                                  edition=None, entry_type="book")
        assert result == "jones2005V02E01"

    def test_inbook_type(self):
        result = calculate_bibkey(surname="Brown", year=2010, volume=None,
                                  edition=2, entry_type="inbook")
        assert result == "brown2010E02"

    def test_incollection_type(self):
        result = calculate_bibkey(surname="Clark", year=2015, volume=None,
                                  edition=1, entry_type="incollection")
        assert result == "clark2015E01"

    def test_collection_type(self):
        result = calculate_bibkey(surname="Lee", year=2018, volume=None,
                                  edition=1, entry_type="collection")
        assert result == "lee2018E01"


# ---------------------------------------------------------------------------
# Article form — basic
# ---------------------------------------------------------------------------

class TestArticleForm:
    def test_article_with_volume(self):
        result = calculate_bibkey(surname="Einstein", year=1905, volume="17",
                                  entry_type="article")
        assert result == "einstein1905V17"

    def test_article_without_volume(self):
        result = calculate_bibkey(surname="Smith", year=2020, volume=None,
                                  entry_type="article")
        assert result == "smith2020"

    def test_report_type_is_article_form(self):
        result = calculate_bibkey(surname="Doe", year=2021, volume=None,
                                  entry_type="report")
        assert result == "doe2021"

    def test_thesis_type_is_article_form(self):
        result = calculate_bibkey(surname="Turing", year=1936, volume=None,
                                  entry_type="thesis")
        assert result == "turing1936"

    def test_online_type_is_article_form(self):
        result = calculate_bibkey(surname="Web", year=2022, volume=None,
                                  entry_type="online")
        assert result == "web2022"

    def test_misc_type_is_article_form(self):
        result = calculate_bibkey(surname="Anon", year=2000, volume=None,
                                  entry_type="misc")
        assert result == "anon2000"


# ---------------------------------------------------------------------------
# Padding
# ---------------------------------------------------------------------------

class TestPadding:
    def test_volume_padded_to_two_digits(self):
        result = calculate_bibkey(surname="Author", year=2000, volume="3",
                                  edition=3, entry_type="book")
        assert "V03" in result

    def test_edition_padded_to_two_digits(self):
        result = calculate_bibkey(surname="Author", year=2000, volume=None,
                                  edition=3, entry_type="book")
        assert "E03" in result

    def test_year_padded_to_four_digits(self):
        result = calculate_bibkey(surname="Author", year=42, volume=None,
                                  edition=1, entry_type="book")
        assert "0042" in result

    def test_large_volume_no_truncation(self):
        # Volume 17 → V17 (two digits, no leading zero needed)
        result = calculate_bibkey(surname="Einstein", year=1905, volume="17",
                                  entry_type="article")
        assert "V17" in result


# ---------------------------------------------------------------------------
# Surname normalisation — von-particle
# ---------------------------------------------------------------------------

class TestVonParticle:
    def test_von_via_name_prefix_arg(self):
        """name_prefix='van' supplied → surname used as-is."""
        result = calculate_bibkey(surname="Beethoven", year=2001, volume=None,
                                  entry_type="article", name_prefix="van")
        assert result == "beethoven2001"

    def test_von_inline_lowercase_prefix_stripped(self):
        """No name_prefix supplied; 'van Beethoven' in surname → strip particle."""
        result = calculate_bibkey(surname="van Beethoven", year=2001, volume=None,
                                  entry_type="article")
        assert result == "beethoven2001"

    def test_von_de_particle_stripped_inline(self):
        result = calculate_bibkey(surname="de Silva", year=2010, volume=None,
                                  entry_type="article")
        assert result == "silva2010"

    def test_uppercase_surname_not_stripped(self):
        """A surname like 'Van' (uppercase) is NOT a particle — keep it."""
        result = calculate_bibkey(surname="Van Morrison", year=1970, volume=None,
                                  entry_type="article")
        assert result == "vanmorrison1970"

    def test_single_word_surname_no_strip(self):
        result = calculate_bibkey(surname="Knuth", year=1997, volume=None,
                                  edition=2, entry_type="book")
        assert result == "knuth1997E02"


# ---------------------------------------------------------------------------
# Surname normalisation — accents
# ---------------------------------------------------------------------------

class TestAccentStripping:
    def test_umlaut_u(self):
        result = calculate_bibkey(surname="Müller", year=2005, volume=None,
                                  entry_type="article")
        assert result == "muller2005"

    def test_umlaut_a(self):
        result = calculate_bibkey(surname="Bär", year=2005, volume=None,
                                  entry_type="article")
        assert result == "bar2005"

    def test_acute_e(self):
        result = calculate_bibkey(surname="Pérez", year=2010, volume=None,
                                  entry_type="article")
        assert result == "perez2010"

    def test_combined_accents_and_particle(self):
        """von particle + accented name."""
        result = calculate_bibkey(surname="Müller", year=2005, volume=None,
                                  entry_type="article", name_prefix="von")
        assert result == "muller2005"


# ---------------------------------------------------------------------------
# Non-numeric volume → absent
# ---------------------------------------------------------------------------

class TestNonNumericVolume:
    def test_roman_numeral_volume_is_absent(self):
        """'II' has no digits → volume absent → no V segment."""
        result = calculate_bibkey(surname="Smith", year=2000, volume="II",
                                  edition=1, entry_type="book")
        assert result == "smith2000E01"
        assert "V" not in result

    def test_ordinal_volume_uses_digits(self):
        """'3rd' → digits='3' → V03 present."""
        result = calculate_bibkey(surname="Smith", year=2000, volume="3rd",
                                  edition=1, entry_type="book")
        assert "V03" in result

    def test_empty_string_volume_is_absent(self):
        result = calculate_bibkey(surname="Smith", year=2000, volume="",
                                  entry_type="article")
        assert result == "smith2000"
        assert "V" not in result

    def test_none_volume_is_absent(self):
        result = calculate_bibkey(surname="Smith", year=2000, volume=None,
                                  entry_type="article")
        assert result == "smith2000"


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------

class TestFallbacks:
    def test_missing_year_is_0000(self):
        result = calculate_bibkey(surname="Doe", year=None, volume=None,
                                  entry_type="article")
        assert result == "doe0000"

    def test_missing_author_is_anon(self):
        result = calculate_bibkey(surname=None, year=2020, volume=None,
                                  entry_type="article")
        assert result == "anon2020"

    def test_missing_author_and_year(self):
        result = calculate_bibkey(surname=None, year=None, volume=None,
                                  entry_type="book", edition=None)
        assert result == "anon0000E01"

    def test_unknown_entry_type_is_article_form(self):
        result = calculate_bibkey(surname="Foo", year=2021, volume=None,
                                  entry_type="customtype")
        assert result == "foo2021"

    def test_none_entry_type_is_article_form(self):
        result = calculate_bibkey(surname="Foo", year=2021, volume=None,
                                  entry_type=None)
        assert result == "foo2021"


# ---------------------------------------------------------------------------
# Entry-type case-insensitivity and @ prefix
# ---------------------------------------------------------------------------

class TestEntryTypeVariants:
    def test_book_uppercase(self):
        result = calculate_bibkey(surname="Author", year=2000, volume=None,
                                  edition=1, entry_type="BOOK")
        assert result.endswith("E01")

    def test_at_book(self):
        result = calculate_bibkey(surname="Author", year=2000, volume=None,
                                  edition=1, entry_type="@book")
        assert result.endswith("E01")

    def test_at_article(self):
        result = calculate_bibkey(surname="Author", year=2000, volume=None,
                                  entry_type="@article")
        assert "E" not in result


# ---------------------------------------------------------------------------
# Integer volume input
# ---------------------------------------------------------------------------

class TestIntVolume:
    def test_integer_volume_coerced(self):
        result = calculate_bibkey(surname="Author", year=2000, volume=3,
                                  edition=1, entry_type="book")
        assert "V03" in result
