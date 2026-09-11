"""Characterization tests for ``parse_md_frontmatter``.

These tests pin the CURRENT behaviour of the function (including its YAML
quirks and unhandled-exception paths) before a behaviour-preserving
complexity refactor. Do not "fix" surprising behaviour here -- if it looks
wrong, that is a signal for a follow-up change request, not for editing
these tests or the source during the refactor.
"""

from __future__ import annotations

import pytest

from workflow.validation.parsers import parse_md_frontmatter, _MAX_FILE_SIZE


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestNoFrontmatter:
    def test_file_without_leading_dashes_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "# Just a heading\n\nSome body text.\n")
        assert parse_md_frontmatter(path) is None

    def test_empty_file_returns_none(self, tmp_path):
        path = _write(tmp_path, "empty.md", "")
        assert parse_md_frontmatter(path) is None

    def test_first_line_dashes_with_trailing_whitespace_is_frontmatter_start(self, tmp_path):
        # `.strip()` is used on line comparisons, so trailing spaces still count.
        path = _write(tmp_path, "note.md", "---   \ntitle: X\n---\n")
        assert parse_md_frontmatter(path) == {"title": "X"}


class TestUnterminatedBlock:
    def test_no_closing_marker_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\ntitle: X\nbody text with no closing marker\n")
        assert parse_md_frontmatter(path) is None

    def test_only_opening_marker_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\n")
        assert parse_md_frontmatter(path) is None


class TestEmptyBlock:
    def test_empty_block_returns_none(self, tmp_path):
        # yaml.safe_load("") -> None, which is not a dict.
        path = _write(tmp_path, "note.md", "---\n---\nBody\n")
        assert parse_md_frontmatter(path) is None

    def test_whitespace_only_block_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\n   \n---\nBody\n")
        assert parse_md_frontmatter(path) is None


class TestNonMappingYaml:
    def test_list_yaml_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\n- one\n- two\n---\nBody\n")
        assert parse_md_frontmatter(path) is None

    def test_scalar_string_yaml_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\njust a scalar string\n---\nBody\n")
        assert parse_md_frontmatter(path) is None

    def test_scalar_int_yaml_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\n42\n---\nBody\n")
        assert parse_md_frontmatter(path) is None


class TestMalformedYaml:
    def test_malformed_yaml_returns_none(self, tmp_path):
        # Unbalanced flow mapping brace triggers a yaml.YAMLError.
        path = _write(tmp_path, "note.md", "---\ntitle: [unclosed\n---\nBody\n")
        assert parse_md_frontmatter(path) is None

    def test_duplicate_tab_indentation_error_returns_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\nkey: value\n\tbad: [1, 2\n---\nBody\n")
        assert parse_md_frontmatter(path) is None


class TestYamlTypeCoercionPitfalls:
    """Pin the exact types PyYAML's safe_load coerces bare scalars into."""

    def test_bare_digit_becomes_int(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\ncount: 5\n---\nBody\n")
        result = parse_md_frontmatter(path)
        assert result == {"count": 5}
        assert type(result["count"]) is int

    def test_bare_float_becomes_float(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\nweight: 3.14\n---\nBody\n")
        result = parse_md_frontmatter(path)
        assert result == {"weight": 3.14}
        assert type(result["weight"]) is float

    def test_yes_no_become_bool(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\nactive: yes\narchived: no\n---\nBody\n")
        result = parse_md_frontmatter(path)
        assert result == {"active": True, "archived": False}
        assert type(result["active"]) is bool
        assert type(result["archived"]) is bool

    def test_true_false_become_bool(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\nactive: true\narchived: false\n---\nBody\n")
        result = parse_md_frontmatter(path)
        assert result == {"active": True, "archived": False}

    def test_empty_value_becomes_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\ntitle:\n---\nBody\n")
        result = parse_md_frontmatter(path)
        assert result == {"title": None}
        assert result["title"] is None

    def test_null_literal_becomes_none(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\ntitle: null\n---\nBody\n")
        result = parse_md_frontmatter(path)
        assert result == {"title": None}

    def test_quoted_digit_stays_string(self, tmp_path):
        path = _write(tmp_path, "note.md", '---\ncount: "5"\n---\nBody\n')
        result = parse_md_frontmatter(path)
        assert result == {"count": "5"}
        assert type(result["count"]) is str


class TestValidFrontmatter:
    def test_simple_mapping_is_parsed(self, tmp_path):
        path = _write(
            tmp_path,
            "note.md",
            "---\ntitle: My Note\ntags:\n  - a\n  - b\n---\nBody content here.\n",
        )
        result = parse_md_frontmatter(path)
        assert result == {"title": "My Note", "tags": ["a", "b"]}

    def test_extra_dashes_line_inside_content_after_close_are_ignored(self, tmp_path):
        path = _write(tmp_path, "note.md", "---\ntitle: X\n---\nBody\n---\nmore text\n")
        result = parse_md_frontmatter(path)
        assert result == {"title": "X"}

    def test_uses_first_closing_marker_not_last(self, tmp_path):
        # end_index is the FIRST subsequent line that is exactly '---'.
        path = _write(tmp_path, "note.md", "---\ntitle: X\n---\nsome body\n---\n")
        result = parse_md_frontmatter(path)
        assert result == {"title": "X"}


class TestFileSizeGuard:
    def test_file_larger_than_max_returns_none(self, tmp_path):
        path = tmp_path / "huge.md"
        padding = "x" * (_MAX_FILE_SIZE + 10)
        path.write_text(f"---\ntitle: X\n---\n{padding}\n", encoding="utf-8")
        assert parse_md_frontmatter(path) is None


class TestOSErrorHandling:
    def test_read_text_oserror_returns_none(self, tmp_path, monkeypatch):
        path = _write(tmp_path, "note.md", "---\ntitle: X\n---\nBody\n")

        def _raise(*args, **kwargs):
            raise OSError("simulated read failure")

        monkeypatch.setattr(type(path), "read_text", _raise)
        assert parse_md_frontmatter(path) is None


class TestNonexistentFileUncaughtBehaviour:
    def test_nonexistent_file_raises_file_not_found_error(self, tmp_path):
        # `.stat()` is called before any try/except, so this currently
        # propagates uncaught. Pinning this so the refactor cannot
        # silently swallow it (or silently change it) without notice.
        missing = tmp_path / "does-not-exist.md"
        with pytest.raises(FileNotFoundError):
            parse_md_frontmatter(missing)
