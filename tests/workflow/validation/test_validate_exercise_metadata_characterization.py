"""Characterization tests for ``validate_exercise_metadata`` (pre-refactor pin).

These tests pin the CURRENT behaviour of branches that were previously
uncovered by the suite, so a behaviour-preserving refactor into smaller
helpers cannot silently change return shape, message text, or ordering.
"""

from workflow.validation.schemas import validate_exercise_metadata

_VALID_BASE = {
    "id": "test-001",
    "type": "multichoice",
    "difficulty": "medium",
    "taxonomy_level": "Usar-Aplicar",
    "taxonomy_domain": "Procedimiento Mental",
}


class TestIdField:
    def test_missing_id_is_error(self):
        data = {k: v for k, v in _VALID_BASE.items() if k != "id"}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["'id' is required and must be a non-empty string"]
        assert warnings == []

    def test_empty_string_id_is_error(self):
        data = {**_VALID_BASE, "id": ""}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["'id' is required and must be a non-empty string"]

    def test_non_string_id_is_error(self):
        data = {**_VALID_BASE, "id": 42}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["'id' is required and must be a non-empty string"]


class TestDifficultyField:
    def test_invalid_difficulty_value_is_error(self):
        data = {**_VALID_BASE, "difficulty": "extreme"}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == [
            "'difficulty' must be one of ['easy', 'hard', 'medium'], got 'extreme'"
        ]
        assert warnings == []


class TestTaxonomyDomainField:
    def test_invalid_taxonomy_domain_value_is_error(self):
        data = {**_VALID_BASE, "taxonomy_domain": "INVALID"}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert len(errors) == 1
        assert errors[0].startswith("'taxonomy_domain' must be one of ")
        assert "got 'INVALID'" in errors[0]


class TestTagsField:
    def test_tags_not_a_list_is_error(self):
        data = {**_VALID_BASE, "tags": "not-a-list"}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["'tags' must be a list"]
        assert warnings == []

    def test_tags_with_non_string_items_is_error(self):
        data = {**_VALID_BASE, "tags": ["ok", 5]}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["all items in 'tags' must be strings"]
        assert warnings == []

    def test_tags_default_empty_when_absent(self):
        result, errors, warnings = validate_exercise_metadata(dict(_VALID_BASE))
        assert result is not None
        assert errors == []
        assert result.tags == ()


class TestConceptsField:
    def test_concepts_not_a_list_is_error(self):
        data = {**_VALID_BASE, "concepts": "not-a-list"}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["'concepts' must be a list"]
        assert warnings == []

    def test_concepts_with_non_string_items_is_error(self):
        data = {**_VALID_BASE, "concepts": ["ok", 5]}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert errors == ["all items in 'concepts' must be strings"]
        assert warnings == []

    def test_concepts_default_empty_when_absent(self):
        result, errors, warnings = validate_exercise_metadata(dict(_VALID_BASE))
        assert result is not None
        assert errors == []
        assert result.concepts == ()


class TestMultipleErrorsOrdering:
    def test_error_ordering_matches_field_check_order(self):
        """id, type, difficulty, taxonomy_level, taxonomy_domain, tags, concepts, status."""
        data = {
            "id": "",
            "type": "",
            "difficulty": "extreme",
            "taxonomy_level": "INVALID",
            "taxonomy_domain": "INVALID",
            "tags": "nope",
            "concepts": "nope",
            "status": "bogus",
        }
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is None
        assert len(errors) == 8
        assert errors[0] == "'id' is required and must be a non-empty string"
        assert errors[1] == "'type' is required and must be a non-empty string"
        assert errors[2].startswith("'difficulty' must be one of")
        assert errors[3].startswith("'taxonomy_level' must be one of")
        assert errors[4].startswith("'taxonomy_domain' must be one of")
        assert errors[5] == "'tags' must be a list"
        assert errors[6] == "'concepts' must be a list"
        assert errors[7].startswith("'status' must be one of")


class TestUnknownKeyWarningsStillWork:
    def test_unknown_key_with_suggestion(self):
        data = {**_VALID_BASE, "diffculty_typo": "x"}
        result, errors, warnings = validate_exercise_metadata(data)
        assert result is not None
        assert errors == []
        assert len(warnings) == 1
        assert "diffculty_typo" in warnings[0]
