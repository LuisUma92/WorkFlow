"""Tests for F1: frontmatter key derivation for note-edge relation types.

Verifies that relation_frontmatter_key() and FRONTMATTER_RELATION_KEYS are
derived from the single source of truth (_STRUCTURAL_RELATION_TYPES_ORDERED /
_ASSOCIATIVE_RELATION_TYPES_ORDERED) and never hard-code the 9 keys.
"""

from __future__ import annotations

import pytest

from workflow.db.models.notes import (
    FRONTMATTER_RELATION_KEYS,
    _ASSOCIATIVE_RELATION_TYPES_ORDERED,
    _STRUCTURAL_RELATION_TYPES_ORDERED,
    relation_frontmatter_key,
)


def test_relation_frontmatter_key_structural_spot_check():
    assert relation_frontmatter_key("structural", "refines") == "derived_from_refines"


def test_relation_frontmatter_key_associative_spot_check():
    assert relation_frontmatter_key("associative", "see_also") == "links_see_also"


def test_relation_frontmatter_key_bad_edge_class_raises():
    with pytest.raises(ValueError):
        relation_frontmatter_key("bogus", "refines")


def test_relation_frontmatter_key_mismatched_relation_type_raises():
    with pytest.raises(ValueError):
        relation_frontmatter_key("structural", "supports")


def test_frontmatter_relation_keys_has_nine_entries():
    assert len(FRONTMATTER_RELATION_KEYS) == 9


def test_frontmatter_relation_keys_round_trip():
    for key, (edge_class, relation_type) in FRONTMATTER_RELATION_KEYS.items():
        assert relation_frontmatter_key(edge_class, relation_type) == key


def test_frontmatter_relation_keys_values_match_derived_pairs():
    expected_pairs = {("structural", rt) for rt in _STRUCTURAL_RELATION_TYPES_ORDERED}
    expected_pairs |= {("associative", rt) for rt in _ASSOCIATIVE_RELATION_TYPES_ORDERED}
    assert set(FRONTMATTER_RELATION_KEYS.values()) == expected_pairs


def test_frontmatter_relation_keys_is_immutable():
    with pytest.raises(TypeError):
        FRONTMATTER_RELATION_KEYS["new_key"] = ("structural", "refines")  # type: ignore[index]


def test_frontmatter_relation_keys_insertion_order():
    expected_order = [
        relation_frontmatter_key("structural", rt) for rt in _STRUCTURAL_RELATION_TYPES_ORDERED
    ] + [
        relation_frontmatter_key("associative", rt) for rt in _ASSOCIATIVE_RELATION_TYPES_ORDERED
    ]
    assert list(FRONTMATTER_RELATION_KEYS.keys()) == expected_order
