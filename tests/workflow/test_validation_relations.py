"""Phase 1 tests — relations + entry_point in NoteFrontmatter (ITEP-0013 DTO)."""

import pytest

from workflow.validation.schemas import validate_note_frontmatter


_BASE = {
    "id": "abc123def456",
    "title": "Test note",
    "type": "permanent",
}


def _note(**extra):
    return {**_BASE, **extra}


# ---------------------------------------------------------------------------
# entry_point
# ---------------------------------------------------------------------------

class TestEntryPoint:
    def test_absent_entry_point_defaults_false(self):
        fm, errors = validate_note_frontmatter(_note())
        assert errors == []
        assert fm.entry_point is False

    def test_entry_point_true(self):
        fm, errors = validate_note_frontmatter(_note(entry_point=True))
        assert errors == []
        assert fm.entry_point is True

    def test_entry_point_false_explicit(self):
        fm, errors = validate_note_frontmatter(_note(entry_point=False))
        assert errors == []
        assert fm.entry_point is False

    def test_entry_point_string_is_error(self):
        _, errors = validate_note_frontmatter(_note(entry_point="yes"))
        assert any("entry_point" in e for e in errors)

    def test_entry_point_integer_is_error(self):
        _, errors = validate_note_frontmatter(_note(entry_point=1))
        assert any("entry_point" in e for e in errors)


# ---------------------------------------------------------------------------
# relations absent / null
# ---------------------------------------------------------------------------

class TestRelationsAbsent:
    def test_no_relations_key_is_valid(self):
        fm, errors = validate_note_frontmatter(_note())
        assert errors == []
        assert fm.relations is None

    def test_null_relations_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(relations=None))
        assert errors == []
        assert fm.relations is None

    def test_empty_relations_dict_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(relations={}))
        assert errors == []
        assert fm.relations is not None
        assert fm.relations.derived_from == ()
        assert fm.relations.links == ()


# ---------------------------------------------------------------------------
# derived_from (structural)
# ---------------------------------------------------------------------------

class TestDerivedFrom:
    def test_valid_derived_from_entry(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "parent001", "type": "continuation"}]
        }))
        assert errors == []
        assert len(fm.relations.derived_from) == 1
        edge = fm.relations.derived_from[0]
        assert edge.id == "parent001"
        assert edge.type == "continuation"
        assert edge.weight is None
        assert edge.note is None

    def test_derived_from_all_structural_types(self):
        for t in ("continuation", "refines", "branches", "synthesis", "rebuttal"):
            fm, errors = validate_note_frontmatter(_note(relations={
                "derived_from": [{"id": "x", "type": t}]
            }))
            assert errors == [], f"type '{t}' should be valid"

    def test_derived_from_with_optional_weight_and_note(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "x", "type": "refines", "weight": 0.9, "note": "tightened"}]
        }))
        assert errors == []
        edge = fm.relations.derived_from[0]
        assert edge.weight == pytest.approx(0.9)
        assert edge.note == "tightened"

    def test_derived_from_missing_id_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"type": "continuation"}]
        }))
        assert any("id" in e for e in errors)

    def test_derived_from_missing_type_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "x"}]
        }))
        assert any("type" in e for e in errors)

    def test_derived_from_invalid_type_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "x", "type": "delivered_from"}]
        }))
        assert any("derived_from" in e or "type" in e for e in errors)

    def test_derived_from_empty_list_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(relations={"derived_from": []}))
        assert errors == []
        assert fm.relations.derived_from == ()

    def test_derived_from_bool_weight_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "x", "type": "refines", "weight": True}]
        }))
        assert any("weight" in e for e in errors)

    def test_derived_from_not_a_list_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={"derived_from": "x"}))
        assert any("derived_from" in e for e in errors)


# ---------------------------------------------------------------------------
# links (associative)
# ---------------------------------------------------------------------------

class TestLinks:
    def test_valid_links_entry(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "links": [{"id": "other001", "type": "supports"}]
        }))
        assert errors == []
        assert len(fm.relations.links) == 1
        edge = fm.relations.links[0]
        assert edge.id == "other001"
        assert edge.type == "supports"

    def test_links_all_associative_types(self):
        for t in ("supports", "contradicts", "expands", "see_also"):
            fm, errors = validate_note_frontmatter(_note(relations={
                "links": [{"id": "x", "type": t}]
            }))
            assert errors == [], f"type '{t}' should be valid"

    def test_links_invalid_type_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "links": [{"id": "x", "type": "continuation"}]  # structural type in associative slot
        }))
        assert any("links" in e or "type" in e for e in errors)

    def test_links_missing_id_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "links": [{"type": "supports"}]
        }))
        assert any("id" in e for e in errors)

    def test_links_empty_list_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(relations={"links": []}))
        assert errors == []
        assert fm.relations.links == ()


# ---------------------------------------------------------------------------
# both families together
# ---------------------------------------------------------------------------

class TestBothFamilies:
    def test_derived_from_and_links_together(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "p", "type": "refines"}],
            "links": [{"id": "q", "type": "contradicts"}],
        }))
        assert errors == []
        assert len(fm.relations.derived_from) == 1
        assert len(fm.relations.links) == 1


# ---------------------------------------------------------------------------
# regression — existing notes still pass
# ---------------------------------------------------------------------------

class TestRegression:
    def test_permanent_note_without_relations_still_valid(self):
        data = {
            "id": "20260101abcd",
            "title": "Some permanent note",
            "type": "permanent",
            "aliases": [],
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
            "main_topic": None,
            "discipline_area": None,
        }
        fm, errors = validate_note_frontmatter(data)
        assert errors == []
        assert fm.relations is None
        assert fm.entry_point is False

    def test_literature_note_without_relations_still_valid(self):
        data = {
            "id": "20260101lit1",
            "title": "A literature note",
            "type": "literature",
            "aliases": [],
            "tags": [],
            "bibkey": "smith2020",
            "origin": "manual",
        }
        fm, errors = validate_note_frontmatter(data)
        assert errors == []
        assert fm.relations is None
