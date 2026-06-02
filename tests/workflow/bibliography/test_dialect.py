"""Unit tests for workflow.bibliography.dialect — BibTeX ↔ BibLaTeX translation.

TDD: RED → GREEN → REFACTOR.
Covers: to_biblatex, to_bibtex, BIBTEX_TO_BIBLATEX, collision warning, immutability.
"""

from __future__ import annotations

import warnings

from workflow.bibliography.dialect import (
    BIBTEX_TO_BIBLATEX,
    classify_entry_type,
    downgrade_entry_type,
    to_biblatex,
    to_bibtex,
)


# ---------------------------------------------------------------------------
# BIBTEX_TO_BIBLATEX map
# ---------------------------------------------------------------------------

class TestBibtexToBiblatexMap:
    def test_all_five_mappings_present(self):
        assert BIBTEX_TO_BIBLATEX["journal"] == "journaltitle"
        assert BIBTEX_TO_BIBLATEX["address"] == "location"
        assert BIBTEX_TO_BIBLATEX["school"] == "institution"
        assert BIBTEX_TO_BIBLATEX["annote"] == "annotation"
        assert BIBTEX_TO_BIBLATEX["note"] == "notes"

    def test_map_has_exactly_five_entries(self):
        assert len(BIBTEX_TO_BIBLATEX) == 5

    def test_values_are_unique(self):
        vals = list(BIBTEX_TO_BIBLATEX.values())
        assert len(vals) == len(set(vals))


# ---------------------------------------------------------------------------
# to_biblatex
# ---------------------------------------------------------------------------

class TestToBiblatex:
    def test_journal_renamed_to_journaltitle(self):
        result = to_biblatex({"journal": "Nature", "title": "X"})
        assert "journaltitle" in result
        assert result["journaltitle"] == "Nature"
        assert "journal" not in result

    def test_address_renamed_to_location(self):
        result = to_biblatex({"address": "New York"})
        assert result["location"] == "New York"
        assert "address" not in result

    def test_school_renamed_to_institution(self):
        result = to_biblatex({"school": "MIT"})
        assert result["institution"] == "MIT"
        assert "school" not in result

    def test_annote_renamed_to_annotation(self):
        result = to_biblatex({"annote": "Some note"})
        assert result["annotation"] == "Some note"
        assert "annote" not in result

    def test_note_renamed_to_notes(self):
        result = to_biblatex({"note": "See also"})
        assert result["notes"] == "See also"
        assert "note" not in result

    def test_unknown_keys_pass_through(self):
        result = to_biblatex({"title": "A Paper", "year": 2020})
        assert result["title"] == "A Paper"
        assert result["year"] == 2020

    def test_biblatex_native_key_untouched(self):
        """If journaltitle is already present (not journal), it passes through."""
        result = to_biblatex({"journaltitle": "Science"})
        assert result["journaltitle"] == "Science"

    def test_all_five_in_one_call(self):
        fields = {
            "journal": "J1",
            "address": "Addr1",
            "school": "School1",
            "annote": "Annote1",
            "note": "Note1",
        }
        result = to_biblatex(fields)
        assert result["journaltitle"] == "J1"
        assert result["location"] == "Addr1"
        assert result["institution"] == "School1"
        assert result["annotation"] == "Annote1"
        assert result["notes"] == "Note1"
        # No bibtex aliases remain
        for k in ("journal", "address", "school", "annote", "note"):
            assert k not in result

    def test_collision_emits_warning_keeps_biblatex_value(self):
        """Both 'journal' and 'journaltitle' present: biblatex value wins + warning."""
        fields = {"journal": "Overridden", "journaltitle": "Keeper"}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = to_biblatex(fields)
        assert len(caught) == 1
        assert issubclass(caught[0].category, UserWarning)
        assert "journal" in str(caught[0].message)
        assert result["journaltitle"] == "Keeper"
        assert "journal" not in result

    def test_collision_note_notes_keeps_notes(self):
        fields = {"note": "alias", "notes": "native"}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = to_biblatex(fields)
        assert len(caught) == 1
        assert result["notes"] == "native"

    def test_immutability_input_not_mutated(self):
        original = {"journal": "X", "title": "Y"}
        original_copy = dict(original)
        to_biblatex(original)
        assert original == original_copy

    def test_returns_new_dict(self):
        d = {"title": "Same"}
        result = to_biblatex(d)
        assert result is not d

    def test_empty_dict(self):
        assert to_biblatex({}) == {}


# ---------------------------------------------------------------------------
# to_bibtex
# ---------------------------------------------------------------------------

class TestToBibtex:
    def test_journaltitle_renamed_to_journal(self):
        result = to_bibtex({"journaltitle": "Nature"})
        assert result["journal"] == "Nature"
        assert "journaltitle" not in result

    def test_location_renamed_to_address(self):
        result = to_bibtex({"location": "Berlin"})
        assert result["address"] == "Berlin"
        assert "location" not in result

    def test_institution_renamed_to_school(self):
        result = to_bibtex({"institution": "MIT"})
        assert result["school"] == "MIT"

    def test_annotation_renamed_to_annote(self):
        result = to_bibtex({"annotation": "a note"})
        assert result["annote"] == "a note"

    def test_notes_renamed_to_note(self):
        result = to_bibtex({"notes": "see also"})
        assert result["note"] == "see also"

    def test_unknown_keys_pass_through(self):
        result = to_bibtex({"title": "T", "year": 2021})
        assert result["title"] == "T"
        assert result["year"] == 2021

    def test_immutability_input_not_mutated(self):
        original = {"journaltitle": "X"}
        original_copy = dict(original)
        to_bibtex(original)
        assert original == original_copy

    def test_returns_new_dict(self):
        d = {"title": "T"}
        result = to_bibtex(d)
        assert result is not d

    def test_empty_dict(self):
        assert to_bibtex({}) == {}


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# downgrade_entry_type
# ---------------------------------------------------------------------------

class TestDowngradeEntryType:
    def test_online_becomes_misc(self):
        assert downgrade_entry_type("online") == "misc"

    def test_report_becomes_techreport(self):
        assert downgrade_entry_type("report") == "techreport"

    def test_thesis_default_phdthesis(self):
        assert downgrade_entry_type("thesis") == "phdthesis"

    def test_thesis_mastersthesis_by_mathesis(self):
        assert downgrade_entry_type("thesis", subtype="mathesis") == "mastersthesis"

    def test_thesis_mastersthesis_by_master_keyword(self):
        assert downgrade_entry_type("thesis", subtype="Master Thesis") == "mastersthesis"

    def test_thesis_phdthesis_explicit_keyword(self):
        assert downgrade_entry_type("thesis", subtype="PhD Dissertation") == "phdthesis"

    def test_mvbook_becomes_book(self):
        assert downgrade_entry_type("mvbook") == "book"

    def test_standard_type_passes_through(self):
        assert downgrade_entry_type("article") == "article"

    def test_unknown_type_passes_through(self):
        assert downgrade_entry_type("customtype") == "customtype"

    def test_case_insensitive(self):
        assert downgrade_entry_type("Online") == "misc"
        assert downgrade_entry_type("REPORT") == "techreport"


# ---------------------------------------------------------------------------
# classify_entry_type
# ---------------------------------------------------------------------------

class TestClassifyEntryType:
    def test_book_is_book(self):
        assert classify_entry_type("book") == "book"

    def test_inbook_is_book(self):
        assert classify_entry_type("inbook") == "book"

    def test_incollection_is_book(self):
        assert classify_entry_type("incollection") == "book"

    def test_collection_is_book(self):
        assert classify_entry_type("collection") == "book"

    def test_book_case_insensitive(self):
        assert classify_entry_type("BOOK") == "book"
        assert classify_entry_type("InBook") == "book"

    def test_at_prefix_tolerated(self):
        assert classify_entry_type("@book") == "book"
        assert classify_entry_type("@inbook") == "book"

    def test_article_is_article(self):
        assert classify_entry_type("article") == "article"

    def test_report_is_article(self):
        assert classify_entry_type("report") == "article"

    def test_thesis_is_article(self):
        assert classify_entry_type("thesis") == "article"

    def test_online_is_article(self):
        assert classify_entry_type("online") == "article"

    def test_misc_is_article(self):
        assert classify_entry_type("misc") == "article"

    def test_unknown_is_article(self):
        assert classify_entry_type("customtype") == "article"

    def test_none_is_article(self):
        assert classify_entry_type(None) == "article"

    def test_whitespace_only_is_article(self):
        """Whitespace-only string strips to '' → not in _BOOK_TYPES → article."""
        assert classify_entry_type("   ") == "article"


class TestRoundTrip:
    def test_bibtex_roundtrip(self):
        """to_bibtex(to_biblatex(x)) == x for pure bibtex-alias fields."""
        original = {
            "journal": "Nature",
            "address": "NYC",
            "school": "MIT",
            "annote": "good",
            "note": "see",
        }
        result = to_bibtex(to_biblatex(original))
        assert result == original

    def test_biblatex_roundtrip(self):
        """to_biblatex(to_bibtex(x)) == x for pure biblatex-native fields."""
        original = {
            "journaltitle": "Nature",
            "location": "NYC",
            "institution": "MIT",
            "annotation": "good",
            "notes": "see",
        }
        result = to_biblatex(to_bibtex(original))
        assert result == original
