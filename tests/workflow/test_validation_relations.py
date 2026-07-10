"""Flat-key relations tests (ITEP-0013 amended 2026-07-09, F3+F4).

zettel_id values in fixtures MUST satisfy the NanoID format
^[A-Za-z0-9_-]{8,21}$ (ITEP-0015) — the validator enforces it, mirroring
the sync/ingest contract in workflow.notes.edges.

Frontmatter schema is 9 FLAT keys (Obsidian Properties cannot represent the
old nested ``relations:`` mapping without corrupting it):

    derived_from_continuation / _refines / _branches / _synthesis / _rebuttal
    links_supports / _contradicts / _expands / _see_also

Each value is a plain list of zettel_id strings. ``weight``/``note`` are
DELIBERATELY absent from frontmatter (decision 2026-07-09).
"""

from workflow.db.models.notes import FRONTMATTER_RELATION_KEYS
from workflow.notes.edges import parse_relations_frontmatter, relations_to_flat_fm
from workflow.validation.schemas import (
    _validate_relations,
    validate_note_frontmatter,
    validate_note_frontmatter_with_warnings,
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
            derived_from_refines=[_PARENT],
        ))
        assert errors == []
        assert fm.entry_point is True
        assert len(fm.relations.derived_from) == 1


# ---------------------------------------------------------------------------
# relations absent
# ---------------------------------------------------------------------------

class TestRelationsAbsent:
    def test_no_relation_keys_is_valid(self):
        fm, errors = validate_note_frontmatter(_note())
        assert errors == []
        assert fm.relations is None


# ---------------------------------------------------------------------------
# derived_from (structural)
# ---------------------------------------------------------------------------

class TestDerivedFrom:
    def test_valid_derived_from_entry(self):
        fm, errors = validate_note_frontmatter(_note(derived_from_continuation=[_PARENT]))
        assert errors == []
        assert len(fm.relations.derived_from) == 1
        edge = fm.relations.derived_from[0]
        assert edge.id == _PARENT
        assert edge.type == "continuation"

    def test_derived_from_all_structural_types(self):
        for t in ("continuation", "refines", "branches", "synthesis", "rebuttal"):
            key = f"derived_from_{t}"
            fm, errors = validate_note_frontmatter(_note(**{key: [_PARENT]}))
            assert errors == [], f"type '{t}' should be valid"
            assert fm.relations.derived_from[0].type == t

    def test_derived_from_wrong_type_list_item_type_error(self):
        # float is a genuinely wrong id type (int/str are valid — see numeric-id
        # regression); the whole-list type guard rejects it.
        _, errors = validate_note_frontmatter(_note(derived_from_continuation=[2026.04]))
        assert any("derived_from_continuation" in e and "zettel ids" in e for e in errors)

    def test_derived_from_short_int_is_format_error(self):
        # 123 is a valid int scalar but fails the NanoID length rule; it is a
        # FORMAT error now (not a "wrong type" error) — the edge is not dropped
        # silently, it is flagged.
        _, errors = validate_note_frontmatter(_note(derived_from_continuation=[123]))
        assert any("derived_from_continuation" in e and "NanoID" in e for e in errors)

    def test_derived_from_dict_value_is_error_mentions_legacy(self):
        _, errors = validate_note_frontmatter(_note(
            derived_from_refines={"id": _PARENT, "type": "refines"}
        ))
        assert any(
            "derived_from_refines" in e and "list of strings" in e and "legacy" in e.lower()
            for e in errors
        )

    def test_derived_from_not_a_list_is_error(self):
        _, errors = validate_note_frontmatter(_note(derived_from_continuation="x"))
        assert any("derived_from_continuation" in e for e in errors)

    def test_derived_from_empty_list_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(derived_from_continuation=[]))
        assert errors == []
        # An empty flat key list still counts as "key present" -> derived_from empty tuple
        assert fm.relations.derived_from == ()

    def test_derived_from_short_id_rejected(self):
        _, errors = validate_note_frontmatter(_note(derived_from_refines=["x"]))
        assert any("NanoID" in e for e in errors)


# ---------------------------------------------------------------------------
# links (associative)
# ---------------------------------------------------------------------------

class TestLinks:
    def test_valid_links_entry(self):
        fm, errors = validate_note_frontmatter(_note(links_supports=[_OTHER]))
        assert errors == []
        assert len(fm.relations.links) == 1
        edge = fm.relations.links[0]
        assert edge.id == _OTHER
        assert edge.type == "supports"

    def test_links_all_associative_types(self):
        for t in ("supports", "contradicts", "expands", "see_also"):
            key = f"links_{t}"
            fm, errors = validate_note_frontmatter(_note(**{key: [_OTHER]}))
            assert errors == [], f"type '{t}' should be valid"
            assert fm.relations.links[0].type == t

    def test_links_empty_list_is_valid(self):
        fm, errors = validate_note_frontmatter(_note(links_supports=[]))
        assert errors == []
        assert fm.relations.links == ()

    def test_links_not_a_list_is_error(self):
        _, errors = validate_note_frontmatter(_note(links_supports={"id": _OTHER}))
        assert any("links_supports" in e for e in errors)


# ---------------------------------------------------------------------------
# both families together
# ---------------------------------------------------------------------------

class TestBothFamilies:
    def test_derived_from_and_links_together(self):
        fm, errors = validate_note_frontmatter(_note(
            derived_from_refines=[_PARENT],
            links_contradicts=[_OTHER],
        ))
        assert errors == []
        assert len(fm.relations.derived_from) == 1
        assert len(fm.relations.links) == 1


# ---------------------------------------------------------------------------
# unknown key warning (difflib suggestion)
# ---------------------------------------------------------------------------

class TestUnknownKeyWarning:
    def test_typo_key_warns_with_suggestion(self):
        fm, errors, warnings = validate_note_frontmatter_with_warnings(
            _note(derived_from_typo=[_PARENT])
        )
        assert errors == []
        assert any("did you mean" in w for w in warnings)
        # unknown key is ignored for parsing purposes (no matching FRONTMATTER key)
        assert fm.relations is None

    def test_unknown_links_key_warns(self):
        _fm, errors, warnings = validate_note_frontmatter_with_warnings(
            _note(links_bogus=[_OTHER])
        )
        assert errors == []
        assert any("links_bogus" in w for w in warnings)

    def test_delegator_drops_warnings(self):
        # The 2-tuple delegator stays byte-identical for existing callers.
        result = validate_note_frontmatter(_note(links_bogus=[_OTHER]))
        assert len(result) == 2
        _fm, errors = result
        assert errors == []


# ---------------------------------------------------------------------------
# legacy nested relations: -> warning, not error
# ---------------------------------------------------------------------------

class TestLegacyNestedWarning:
    def test_nested_relations_block_warns_not_errors(self):
        fm, errors, warnings = validate_note_frontmatter_with_warnings(
            _note(relations={"derived_from": [{"id": _PARENT, "type": "refines"}]})
        )
        assert errors == []
        assert any("legacy nested relations" in w for w in warnings)
        # nested block is never descended by the flat validator
        assert fm.relations is None

    def test_corrupted_relations_string_warns_not_errors(self):
        fm, errors, warnings = validate_note_frontmatter_with_warnings(
            _note(relations="derived_from_refines")
        )
        assert errors == []
        assert any("legacy nested relations" in w for w in warnings)
        assert fm.relations is None

    def test_empty_relations_dict_no_warning(self):
        # An empty dict is not "legacy present" per has_legacy_relations semantics.
        _fm, errors, warnings = validate_note_frontmatter_with_warnings(
            _note(relations={})
        )
        assert errors == []
        assert not any("legacy nested relations" in w for w in warnings)


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


# ---------------------------------------------------------------------------
# _validate_relations helper — direct exercise (lenient collect)
# ---------------------------------------------------------------------------

class TestValidateRelationsHelper:
    def test_mixed_valid_invalid_items_collects_valid(self):
        errors: list[str] = []
        relations = _validate_relations(
            {
                "id": "abc123def456",
                "title": "t",
                "derived_from_refines": [_PARENT, "x"],  # second id malformed
            },
            errors,
        )
        assert relations is not None
        assert len(relations.derived_from) == 1
        assert relations.derived_from[0].id == _PARENT
        assert any("NanoID" in e for e in errors)


# ---------------------------------------------------------------------------
# round-trip: flat fm -> parse_relations_frontmatter -> relations_to_flat_fm
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_flat_dict_round_trips_through_entries(self):
        flat = {
            "derived_from_refines": [_PARENT],
            "links_supports": [_OTHER, _SECOND],
        }
        entries = parse_relations_frontmatter(flat)
        assert relations_to_flat_fm(entries) == flat

    def test_all_nine_keys_are_recognized(self):
        assert len(FRONTMATTER_RELATION_KEYS) == 9


# ---------------------------------------------------------------------------
# CLI: legacy warning goes to stderr, exit stays 0
# ---------------------------------------------------------------------------

class TestValidateNotesCliLegacyWarning:
    def _write(self, path, extra):
        path.write_text(
            "---\nid: cliwarn00001\ntitle: Legacy note\ntype: permanent\n"
            f"{extra}\n---\nbody\n",
            encoding="utf-8",
        )

    def test_nested_relations_prints_stderr_warning_exit_0(self, global_engine, tmp_path):
        from click.testing import CliRunner

        from workflow.validation.cli import validate

        self._write(
            tmp_path / "n.md",
            "relations:\n  derived_from:\n    - id: parent000001\n      type: refines",
        )
        result = CliRunner().invoke(
            validate,
            ["notes", str(tmp_path)],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stderr
        assert "legacy nested relations" in result.stderr
        assert "legacy nested relations" not in result.stdout


class TestNumericZettelId:
    """Timestamp-style ids (bare digits) parse as int under YAML — F5 regression."""

    def test_unquoted_int_id_validates_with_zero_errors(self):
        fm, errors = validate_note_frontmatter(
            _note(derived_from_refines=[202604010900])
        )
        assert errors == []
        assert fm is not None
        assert fm.relations is not None
        ids = [e.id for e in fm.relations.derived_from]
        assert ids == ["202604010900"]
        assert isinstance(fm.relations.derived_from[0].id, str)

    def test_int_id_via_validate_relations_helper(self):
        errors: list[str] = []
        rel = _validate_relations({"links_supports": [202604010900]}, errors)
        assert errors == []
        assert rel is not None
        assert [e.id for e in rel.links] == ["202604010900"]
        assert isinstance(rel.links[0].id, str)
