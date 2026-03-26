"""Tests for workflow.exercise.generator — exercise file generator.

TDD: these tests are written BEFORE the implementation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from workflow.exercise.generator import (
    GeneratedExercise,
    generate_exercise_file,
    generate_from_content,
)
from workflow.exercise.parser import parse_exercise


# ---------------------------------------------------------------------------
# generate_exercise_file
# ---------------------------------------------------------------------------


def test_generate_single_file_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        result = generate_exercise_file(out, "my-ex-001")
        assert result.file_path.exists()
        assert result.created is True
        assert result.exercise_id == "my-ex-001"


def test_generate_single_file_correct_yaml_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(
            out,
            "serway-ch01-005",
            exercise_type="essay",
            difficulty="medium",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
            tags=["physics"],
        )
        content = (out / "serway-ch01-005.tex").read_text()
        assert "id: serway-ch01-005" in content
        assert "type: essay" in content
        assert "difficulty: medium" in content
        assert "taxonomy_level: Usar-Aplicar" in content
        assert "taxonomy_domain: Procedimiento Mental" in content
        assert "tags: [physics]" in content
        assert "status: placeholder" in content


def test_generate_file_has_question_skeleton():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(out, "ex-001")
        content = (out / "ex-001.tex").read_text()
        assert r"\question{" in content


def test_generate_file_has_exa_when_chapter_and_num_provided():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(out, "serway-ch01-005", chapter=1, exercise_num=5)
        content = (out / "serway-ch01-005.tex").read_text()
        assert r"\exa[1]{5}" in content


def test_generate_file_no_exa_when_chapter_missing():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(out, "generic-001")
        content = (out / "generic-001.tex").read_text()
        assert r"\exa" not in content


def test_generate_file_has_book_cite():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(
            out, "serway-ch01-005", book_cite="serway", chapter=1, exercise_num=5
        )
        content = (out / "serway-ch01-005.tex").read_text()
        assert r"\cite{serway}" in content


def test_generate_skips_existing_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        path = out / "ex-001.tex"
        path.write_text("EXISTING CONTENT")

        result = generate_exercise_file(out, "ex-001")

        assert result.created is False
        # File must not be overwritten
        assert path.read_text() == "EXISTING CONTENT"


def test_generate_file_has_ifthenelse_guard():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(out, "ex-001")
        content = (out / "ex-001.tex").read_text()
        assert r"\ifthenelse{\boolean{main}}" in content


def test_generate_file_tags_empty_list():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(out, "ex-002", tags=[])
        content = (out / "ex-002.tex").read_text()
        assert "tags: []" in content


def test_generate_file_no_tags_defaults_empty():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(out, "ex-003")
        content = (out / "ex-003.tex").read_text()
        assert "tags:" in content


# ---------------------------------------------------------------------------
# generate_from_content — range generation
# ---------------------------------------------------------------------------


def test_generate_from_content_creates_correct_number_of_files():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        results = generate_from_content(
            out, "serway", chapter=1, first_exercise=1, last_exercise=5
        )
        assert len(results) == 5
        assert all(r.created for r in results)


def test_generate_from_content_naming_convention():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        results = generate_from_content(
            out, "serway", chapter=3, first_exercise=10, last_exercise=12
        )
        names = {r.file_path.name for r in results}
        assert names == {
            "serway-ch03-010.tex",
            "serway-ch03-011.tex",
            "serway-ch03-012.tex",
        }


def test_generate_from_content_files_contain_exa():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        results = generate_from_content(
            out, "serway", chapter=1, first_exercise=1, last_exercise=2
        )
        content_1 = results[0].file_path.read_text()
        content_2 = results[1].file_path.read_text()
        assert r"\exa[1]{1}" in content_1
        assert r"\exa[1]{2}" in content_2


def test_generate_from_content_skips_existing():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        existing = out / "serway-ch01-001.tex"
        existing.write_text("PRE-EXISTING")

        results = generate_from_content(
            out, "serway", chapter=1, first_exercise=1, last_exercise=3
        )

        created = [r for r in results if r.created]
        skipped = [r for r in results if not r.created]
        assert len(created) == 2
        assert len(skipped) == 1
        assert existing.read_text() == "PRE-EXISTING"


# ---------------------------------------------------------------------------
# Round-trip: generated file must be parseable
# ---------------------------------------------------------------------------


def test_generated_file_is_parseable():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_exercise_file(
            out,
            "roundtrip-001",
            exercise_type="essay",
            difficulty="medium",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
            tags=["test"],
            book_cite="serway",
            chapter=1,
            exercise_num=1,
        )
        content = (out / "roundtrip-001.tex").read_text()
        result = parse_exercise(content, source_path="roundtrip-001.tex")

        assert not result.errors, f"Parse errors: {result.errors}"
        assert result.exercise is not None
        assert result.exercise.metadata is not None
        assert result.exercise.metadata.id == "roundtrip-001"
        assert result.exercise.status == "placeholder"


# ---------------------------------------------------------------------------
# Security: path traversal rejection
# ---------------------------------------------------------------------------


def test_exercise_id_path_traversal_rejected(tmp_path):
    """Exercise IDs with path separators should be rejected."""
    with pytest.raises(ValueError, match="unsafe characters"):
        generate_exercise_file(tmp_path, "../../../evil")


def test_exercise_id_with_dots_allowed(tmp_path):
    """Exercise IDs with dots (but no slashes) should be allowed."""
    result = generate_exercise_file(tmp_path, "phys.gauss.001")
    assert result.created is True
