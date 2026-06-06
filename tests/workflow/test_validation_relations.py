"""Phase 1 tests — relations + entry_point in NoteFrontmatter (ITEP-0013 DTO).

zettel_id values in fixtures MUST satisfy the NanoID format
^[A-Za-z0-9_-]{8,21}$ (ITEP-0015) — the validator now enforces it, mirroring
the sync/ingest contract in workflow.notes.edges.
"""

import pytest

from workflow.validation.schemas import (
    _validate_relations,
    validate_note_frontmatter,
)


_BASE = {
    "id": "abc123def456",
    "title": "Test note",
    "type": "permanent",
}

# Valid NanoID-shaped ids for fixtures.
_PARENT = "parent000001"
_OTHER = "other0000001"
_SECOND = "second000002"


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

    def test_entry_point_null_is_error(self):
        # key present with empty value → None (default only fires on absent key)
        _, errors = validate_note_frontmatter(_note(entry_point=None))
        assert any("entry_point" in e for e in errors)

    def test_entry_point_true_with_relations(self):
        fm, errors = validate_note_frontmatter(_note(
            entry_point=True,
            relations={"derived_from": [{"id": _PARENT, "type": "refines"}]},
        ))
        assert errors == []
        assert fm.entry_point is True
        assert len(fm.relations.derived_from) == 1


# ---------------------------------------------------------------------------
# relations absent / null / malformed top-level
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

    def test_relations_as_list_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations=[{"id": _PARENT}]))
        assert any("relations" in e and "mapping" in e for e in errors)


# ---------------------------------------------------------------------------
# derived_from (structural)
# ---------------------------------------------------------------------------

class TestDerivedFrom:
    def test_valid_derived_from_entry(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "continuation"}]
        }))
        assert errors == []
        assert len(fm.relations.derived_from) == 1
        edge = fm.relations.derived_from[0]
        assert edge.id == _PARENT
        assert edge.type == "continuation"
        assert edge.weight is None
        assert edge.note is None

    def test_derived_from_all_structural_types(self):
        for t in ("continuation", "refines", "branches", "synthesis", "rebuttal"):
            fm, errors = validate_note_frontmatter(_note(relations={
                "derived_from": [{"id": _PARENT, "type": t}]
            }))
            assert errors == [], f"type '{t}' should be valid"
            assert fm.relations.derived_from[0].type == t

    def test_derived_from_with_optional_weight_and_note(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "refines", "weight": 0.9, "note": "tightened"}]
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
            "derived_from": [{"id": _PARENT}]
        }))
        assert any("type" in e for e in errors)

    def test_derived_from_rejects_associative_type(self):
        # associative type ('supports') in a structural slot must fail
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "supports"}]
        }))
        assert any("derived_from" in e and "invalid type" in e for e in errors)

    def test_derived_from_invalid_type_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "delivered_from"}]
        }))
        assert any("derived_from" in e and "invalid type" in e for e in errors)

    def test_derived_from_empty_list_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(relations={"derived_from": []}))
        assert errors == []
        assert fm.relations.derived_from == ()

    def test_derived_from_not_a_list_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={"derived_from": "x"}))
        assert any("derived_from" in e for e in errors)

    def test_derived_from_non_dict_item_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": ["just_a_string"]
        }))
        assert any("derived_from" in e and "mapping" in e for e in errors)

    def test_derived_from_bool_weight_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "refines", "weight": True}]
        }))
        assert any("weight" in e for e in errors)

    def test_derived_from_string_weight_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "refines", "weight": "heavy"}]
        }))
        assert any("weight" in e for e in errors)

    def test_derived_from_non_string_note_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "refines", "note": 123}]
        }))
        assert any("note" in e for e in errors)

    def test_derived_from_short_id_rejected(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": "x", "type": "refines"}]
        }))
        assert any("NanoID" in e for e in errors)


# ---------------------------------------------------------------------------
# links (associative)
# ---------------------------------------------------------------------------

class TestLinks:
    def test_valid_links_entry(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "links": [{"id": _OTHER, "type": "supports"}]
        }))
        assert errors == []
        assert len(fm.relations.links) == 1
        edge = fm.relations.links[0]
        assert edge.id == _OTHER
        assert edge.type == "supports"

    def test_links_all_associative_types(self):
        for t in ("supports", "contradicts", "expands", "see_also"):
            fm, errors = validate_note_frontmatter(_note(relations={
                "links": [{"id": _OTHER, "type": t}]
            }))
            assert errors == [], f"type '{t}' should be valid"
            assert fm.relations.links[0].type == t

    def test_links_rejects_structural_type(self):
        # structural type ('continuation') in an associative slot must fail
        _, errors = validate_note_frontmatter(_note(relations={
            "links": [{"id": _OTHER, "type": "continuation"}]
        }))
        assert any("links" in e and "invalid type" in e for e in errors)

    def test_links_missing_id_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={
            "links": [{"type": "supports"}]
        }))
        assert any("id" in e for e in errors)

    def test_links_empty_list_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(relations={"links": []}))
        assert errors == []
        assert fm.relations.links == ()

    def test_links_not_a_list_is_error(self):
        _, errors = validate_note_frontmatter(_note(relations={"links": {"id": _OTHER}}))
        assert any("links" in e for e in errors)


# ---------------------------------------------------------------------------
# both families together + lenient collect
# ---------------------------------------------------------------------------

class TestBothFamilies:
    def test_derived_from_and_links_together(self):
        fm, errors = validate_note_frontmatter(_note(relations={
            "derived_from": [{"id": _PARENT, "type": "refines"}],
            "links": [{"id": _OTHER, "type": "contradicts"}],
        }))
        assert errors == []
        assert len(fm.relations.derived_from) == 1
        assert len(fm.relations.links) == 1


class TestLenientCollect:
    def test_mixed_valid_invalid_items_collects_valid(self):
        # _validate_relations builds the valid sibling AND reports the error;
        # validate_note_frontmatter discards the DTO when errors exist, so we
        # exercise the helper directly to pin both behaviours.
        errors: list[str] = []
        relations = _validate_relations(
            {"relations": {"derived_from": [
                {"id": _PARENT, "type": "refines"},      # valid
                {"id": _SECOND, "type": "bogus_type"},   # invalid
            ]}},
            errors,
        )
        assert relations is not None
        assert len(relations.derived_from) == 1            # valid sibling survived
        assert relations.derived_from[0].id == _PARENT
        assert any("invalid type" in e for e in errors)    # error still recorded


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
