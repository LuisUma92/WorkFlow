"""Tests for workflow.validation — schemas and parsers."""
import pytest
from pathlib import Path


class TestExerciseMetadataValidation:
    def test_valid_exercise_metadata(self):
        from workflow.validation.schemas import validate_exercise_metadata
        data = {
            "id": "test-001",
            "type": "multichoice",
            "difficulty": "medium",
            "taxonomy_level": "Usar-Aplicar",
            "taxonomy_domain": "Procedimiento Mental",
        }
        result, errors = validate_exercise_metadata(data)
        assert result is not None
        assert errors == []

    def test_invalid_taxonomy_level(self):
        from workflow.validation.schemas import validate_exercise_metadata
        data = {
            "id": "test-002",
            "type": "essay",
            "difficulty": "easy",
            "taxonomy_level": "INVALID",
            "taxonomy_domain": "Información",
        }
        result, errors = validate_exercise_metadata(data)
        assert result is None
        assert any("taxonomy_level" in e for e in errors)

    def test_all_taxonomy_levels_valid(self):
        """All taxonomy levels from academic model are accepted by validation."""
        from workflow.validation.schemas import _VALID_TAXONOMY_LEVELS
        from workflow.db.models.academic import _TAXONOMY_LEVELS
        assert set(_TAXONOMY_LEVELS) == _VALID_TAXONOMY_LEVELS

    def test_all_taxonomy_domains_valid(self):
        """All taxonomy domains from academic model are accepted by validation."""
        from workflow.validation.schemas import _VALID_TAXONOMY_DOMAINS
        from workflow.db.models.academic import _TAXONOMY_DOMAINS
        assert set(_TAXONOMY_DOMAINS) == _VALID_TAXONOMY_DOMAINS


class TestNoteFrontmatterValidation:
    def test_valid_note(self):
        from workflow.validation.schemas import validate_note_frontmatter
        data = {"id": "note-001", "title": "Test Note"}
        result, errors = validate_note_frontmatter(data)
        assert result is not None
        assert errors == []


class TestTexMetadataParser:
    def test_parse_tex_with_yaml(self, tmp_path):
        from workflow.validation.parsers import parse_tex_metadata
        tex_file = tmp_path / "test.tex"
        tex_file.write_text("% ---\n% id: test-001\n% type: essay\n% ---\n\\question{s}{s}\n")
        result = parse_tex_metadata(tex_file)
        assert result is not None
        assert result["id"] == "test-001"

    def test_parse_tex_no_yaml(self, tmp_path):
        from workflow.validation.parsers import parse_tex_metadata
        tex_file = tmp_path / "plain.tex"
        tex_file.write_text("\\section{Hello}\n")
        result = parse_tex_metadata(tex_file)
        assert result is None

    def test_parse_tex_nonexistent(self, tmp_path):
        from workflow.validation.parsers import parse_tex_metadata
        result = parse_tex_metadata(tmp_path / "nonexistent.tex")
        assert result is None
