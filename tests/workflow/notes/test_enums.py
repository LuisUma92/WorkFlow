"""Tests for `workflow notes enums` command and edge_class_for_relation_type() helper.

Includes ITEP-0015 drift-guard: asserts CLI vocab == NoteEdge CHECK constraints.
"""

from __future__ import annotations

import json
import re

import pytest
from click.testing import CliRunner

from workflow.notes.cli import notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_in_values(sqltext: str) -> set[str]:
    """Extract single-quoted values from a SQL IN clause string."""
    return set(re.findall(r"'([^']+)'", sqltext))


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Task 1: enums --json shape
# ---------------------------------------------------------------------------

class TestEnumsJson:
    def test_exit_zero(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        assert result.exit_code == 0, result.output

    def test_valid_json(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_has_required_top_level_keys(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        for key in ("edge_class", "relation_type", "note_type", "zettel_id_format"):
            assert key in data, f"missing key: {key}"

    def test_edge_class_values(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert set(data["edge_class"]) == {"structural", "associative"}

    def test_relation_type_structural(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert set(data["relation_type"]["structural"]) == {
            "continuation", "refines", "branches", "synthesis", "rebuttal"
        }

    def test_relation_type_associative(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert set(data["relation_type"]["associative"]) == {
            "supports", "contradicts", "expands", "see_also"
        }

    def test_note_type_values(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert set(data["note_type"]) == {"fleeting", "literature", "permanent"}

    def test_zettel_id_format_keys(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        zf = data["zettel_id_format"]
        for key in (
            "library", "alphabet", "default_length",
            "min_length", "max_length", "validation_regex",
            "filename_convention", "alias_template",
        ):
            assert key in zf, f"missing zettel_id_format key: {key}"

    def test_zettel_id_format_values(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        zf = data["zettel_id_format"]
        assert zf["library"] == "nanoid"
        assert zf["alphabet"] == "A-Za-z0-9_-"
        assert zf["default_length"] == 12
        assert zf["min_length"] == 8
        assert zf["max_length"] == 21
        assert zf["validation_regex"] == "^[A-Za-z0-9_-]{8,21}$"
        assert zf["filename_convention"] == "<zettel_id>-<slug>.md"
        assert zf["alias_template"] == [
            "<zettel_id>-<slug>", "<slug>", "<zettel_id>"
        ]

    def test_no_db_needed(self, runner):
        """enums command must not require a DB (no engine/session)."""
        result = runner.invoke(notes, ["enums", "--json"])
        assert result.exit_code == 0
        assert "Error" not in result.output

    def test_pre_existing_keys_unchanged(self, runner):
        """Additive contract: pre-existing keys must still be present with same values."""
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert set(data["edge_class"]) == {"structural", "associative"}
        assert set(data["relation_type"]["structural"]) == {
            "continuation", "refines", "branches", "synthesis", "rebuttal"
        }
        assert set(data["relation_type"]["associative"]) == {
            "supports", "contradicts", "expands", "see_also"
        }
        assert set(data["note_type"]) == {"fleeting", "literature", "permanent"}
        assert "zettel_id_format" in data


class TestFrontmatterRelationKeysJson:
    def test_key_present(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert "frontmatter_relation_keys" in data

    def test_derived_from_source_of_truth(self, runner):
        from workflow.db.models.notes import FRONTMATTER_RELATION_KEYS

        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        frk = data["frontmatter_relation_keys"]

        assert set(frk.keys()) == set(FRONTMATTER_RELATION_KEYS.keys())
        for key, (edge_class, relation_type) in FRONTMATTER_RELATION_KEYS.items():
            assert frk[key] == {
                "edge_class": edge_class,
                "relation_type": relation_type,
            }, f"mismatch for {key!r}"

    def test_order_matches_source_of_truth(self, runner):
        from workflow.db.models.notes import FRONTMATTER_RELATION_KEYS

        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        frk = data["frontmatter_relation_keys"]

        assert list(frk.keys()) == list(FRONTMATTER_RELATION_KEYS.keys())

    def test_structural_then_associative_ordering(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        keys = list(data["frontmatter_relation_keys"].keys())
        structural_keys = [k for k in keys if k.startswith("derived_from_")]
        associative_keys = [k for k in keys if k.startswith("links_")]
        assert keys == structural_keys + associative_keys
        assert len(structural_keys) == 5
        assert len(associative_keys) == 4

    def test_relation_key_prefixes_present(self, runner):
        from workflow.db.models.notes import (
            STRUCTURAL_KEY_PREFIX,
            ASSOCIATIVE_KEY_PREFIX,
        )

        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        assert "relation_key_prefixes" in data
        assert data["relation_key_prefixes"] == {
            "structural": STRUCTURAL_KEY_PREFIX,
            "associative": ASSOCIATIVE_KEY_PREFIX,
        }


class TestFrontmatterRelationKeysHuman:
    def test_contains_flat_keys(self, runner):
        from workflow.db.models.notes import FRONTMATTER_RELATION_KEYS

        result = runner.invoke(notes, ["enums"])
        for key in FRONTMATTER_RELATION_KEYS:
            assert key in result.output, f"missing flat key: {key}"

    def test_contains_section_heading(self, runner):
        result = runner.invoke(notes, ["enums"])
        assert "Frontmatter relation keys:" in result.output


# ---------------------------------------------------------------------------
# Task 1: enums human-readable (non-json)
# ---------------------------------------------------------------------------

class TestEnumsHuman:
    def test_exit_zero(self, runner):
        result = runner.invoke(notes, ["enums"])
        assert result.exit_code == 0, result.output

    def test_contains_relation_types(self, runner):
        result = runner.invoke(notes, ["enums"])
        for rt in ("continuation", "refines", "branches", "synthesis", "rebuttal",
                   "supports", "contradicts", "expands", "see_also"):
            assert rt in result.output, f"missing: {rt}"

    def test_contains_edge_classes(self, runner):
        result = runner.invoke(notes, ["enums"])
        assert "structural" in result.output
        assert "associative" in result.output

    def test_contains_note_types(self, runner):
        result = runner.invoke(notes, ["enums"])
        assert "permanent" in result.output
        assert "literature" in result.output
        assert "fleeting" in result.output


# ---------------------------------------------------------------------------
# ITEP-0015 DRIFT GUARD: CLI vocab == NoteEdge CHECK constraints
# ---------------------------------------------------------------------------

class TestEnumsDriftGuard:
    """Assert that the enums command output equals what the DB CHECK constraints enforce.

    This test will fail if someone edits STRUCTURAL_RELATION_TYPES or EDGE_CLASSES
    without updating the NoteEdge model constraints (or vice versa).
    """

    def _get_check_constraint_text(self, name: str) -> str:
        from workflow.db.models.notes import NoteEdge
        table = NoteEdge.__table__
        for constraint in table.constraints:
            if getattr(constraint, "name", None) == name:
                return str(constraint.sqltext)
        raise AssertionError(f"Constraint {name!r} not found on NoteEdge.__table__")

    def test_edge_class_matches_db_check(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        cli_classes = set(data["edge_class"])

        db_text = self._get_check_constraint_text("ck_note_edge_class_valid")
        db_classes = _parse_in_values(db_text)

        assert cli_classes == db_classes, (
            f"CLI edge_class {cli_classes!r} != DB constraint {db_classes!r}"
        )

    def test_relation_type_matches_db_check(self, runner):
        result = runner.invoke(notes, ["enums", "--json"])
        data = json.loads(result.output)
        cli_rel_types = (
            set(data["relation_type"]["structural"])
            | set(data["relation_type"]["associative"])
        )

        db_text = self._get_check_constraint_text("ck_note_edge_relation_type_valid")
        db_rel_types = _parse_in_values(db_text)

        assert cli_rel_types == db_rel_types, (
            f"CLI relation_types {cli_rel_types!r} != DB constraint {db_rel_types!r}"
        )


# ---------------------------------------------------------------------------
# Task 3: edge_class_for_relation_type() helper
# ---------------------------------------------------------------------------

class TestEdgeClassForRelationType:
    def test_structural_types(self):
        from workflow.db.models.notes import edge_class_for_relation_type
        for rt in ("continuation", "refines", "branches", "synthesis", "rebuttal"):
            assert edge_class_for_relation_type(rt) == "structural", f"failed for {rt!r}"

    def test_associative_types(self):
        from workflow.db.models.notes import edge_class_for_relation_type
        for rt in ("supports", "contradicts", "expands", "see_also"):
            assert edge_class_for_relation_type(rt) == "associative", f"failed for {rt!r}"

    def test_unknown_returns_none(self):
        from workflow.db.models.notes import edge_class_for_relation_type
        assert edge_class_for_relation_type("unknown_type") is None
        assert edge_class_for_relation_type("") is None
        assert edge_class_for_relation_type("STRUCTURAL") is None  # case-sensitive
