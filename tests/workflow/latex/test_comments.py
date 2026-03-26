"""Tests for workflow.latex.comments — commented YAML extraction."""

import pytest

from workflow.latex.comments import extract_commented_yaml, strip_comments


class TestExtractCommentedYaml:
    """extract_commented_yaml(text) → (dict | None, remaining_text)."""

    def test_basic_yaml_block(self):
        text = (
            "% ---\n"
            "% id: phys-gauss-001\n"
            "% type: multichoice\n"
            "% difficulty: medium\n"
            "% ---\n"
            "\\question{stem}{sol}\n"
        )
        metadata, rest = extract_commented_yaml(text)
        assert metadata is not None
        assert metadata["id"] == "phys-gauss-001"
        assert metadata["type"] == "multichoice"
        assert metadata["difficulty"] == "medium"
        assert "\\question" in rest

    def test_yaml_with_lists(self):
        text = (
            "% ---\n"
            "% id: ex-001\n"
            "% tags: [physics, electrostatics]\n"
            "% concepts:\n"
            "%   - 20260320-physics-gauss-law\n"
            "%   - 20260321-coulomb\n"
            "% ---\n"
            "rest\n"
        )
        metadata, rest = extract_commented_yaml(text)
        assert metadata["tags"] == ["physics", "electrostatics"]
        assert len(metadata["concepts"]) == 2

    def test_yaml_with_taxonomy(self):
        text = (
            "% ---\n"
            "% id: ex-002\n"
            "% taxonomy_level: Usar-Aplicar\n"
            "% taxonomy_domain: Procedimiento Mental\n"
            "% ---\n"
        )
        metadata, _ = extract_commented_yaml(text)
        assert metadata["taxonomy_level"] == "Usar-Aplicar"
        assert metadata["taxonomy_domain"] == "Procedimiento Mental"

    def test_no_yaml_block(self):
        text = "\\question{stem}{sol}\n"
        metadata, rest = extract_commented_yaml(text)
        assert metadata is None
        assert rest == text

    def test_yaml_block_with_status(self):
        text = "% ---\n% id: ex-003\n% status: complete\n% ---\n"
        metadata, _ = extract_commented_yaml(text)
        assert metadata["status"] == "complete"

    def test_preserves_content_after_yaml(self):
        text = (
            "% ---\n"
            "% id: ex-004\n"
            "% ---\n"
            "\\ifthenelse{\\boolean{main}}{\n"
            "  \\exa[1]{5}\n"
            "}{\n"
            "}\n"
        )
        metadata, rest = extract_commented_yaml(text)
        assert metadata["id"] == "ex-004"
        assert "\\ifthenelse" in rest

    def test_comment_lines_outside_yaml_preserved(self):
        """Regular comments (not YAML) should not be consumed."""
        text = (
            "% This is a regular comment\n"
            "% ---\n"
            "% id: ex-005\n"
            "% ---\n"
            "% Another regular comment\n"
            "content\n"
        )
        metadata, rest = extract_commented_yaml(text)
        assert metadata["id"] == "ex-005"
        assert "Another regular comment" in rest

    def test_empty_yaml_block(self):
        text = "% ---\n% ---\ncontent\n"
        metadata, rest = extract_commented_yaml(text)
        assert metadata == {}
        assert "content" in rest

    def test_invalid_yaml_returns_none(self):
        """Malformed YAML in comment block returns None metadata."""
        text = "% ---\n% key: [unclosed bracket\n% ---\ncontent\n"
        metadata, rest = extract_commented_yaml(text)
        assert metadata is None
        assert "content" in rest


class TestStripComments:
    """strip_comments(text) → text with % comment lines removed."""

    def test_strips_comment_lines(self):
        text = "real line\n% comment\nanother line\n"
        result = strip_comments(text)
        assert result == "real line\nanother line\n"

    def test_preserves_percent_in_content(self):
        """Percent in math or mid-line should not be stripped."""
        text = "100\\% of the time\n"
        result = strip_comments(text)
        assert result == "100\\% of the time\n"

    def test_strips_only_full_line_comments(self):
        text = "  % indented comment\nreal content\n"
        result = strip_comments(text)
        assert result == "real content\n"

    def test_escaped_percent_at_line_start_preserved(self):
        text = "\\% this is not a comment\nreal line\n"
        result = strip_comments(text)
        assert "\\% this is not a comment" in result

    def test_empty_input(self):
        assert strip_comments("") == ""
