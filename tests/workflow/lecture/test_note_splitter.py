"""Tests for workflow.lecture.note_splitter — Phase 5d."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from workflow.lecture.note_splitter import SplitFile, SplitResult, split_notes_file


def _make_source(tmp_path: Path, content: str, name: str = "notes.tex") -> Path:
    src = tmp_path / name
    src.write_text(dedent(content))
    return src


# ── basic split ─────────────────────────────────────────────────────────────


def test_split_basic(tmp_path: Path) -> None:
    """File with 2 markers produces 2 output files."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/intro.tex
        line A1
        line A2
        %>lect/tex/body.tex
        line B1
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert isinstance(result, SplitResult)
    assert len(result.files) == 2
    paths = {f.output_path.name for f in result.files}
    assert paths == {"intro.tex", "body.tex"}


def test_split_with_end_marker(tmp_path: Path) -> None:
    """%%>END stops the current section without starting a new one."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/intro.tex
        line 1
        %>END
        orphan line
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert len(result.files) == 1
    content = result.files[0].output_path.read_text()
    assert "line 1" in content
    assert "orphan line" not in content


def test_split_generates_import_lines(tmp_path: Path) -> None:
    """SplitResult.import_lines contains correct \\input{} lines."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/intro.tex
        content
        %>lect/tex/body.tex
        more
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert len(result.import_lines) == 2
    assert any("intro.tex" in line for line in result.import_lines)
    assert any("body.tex" in line for line in result.import_lines)
    for line in result.import_lines:
        assert "\\input{" in line


def test_split_preserves_content(tmp_path: Path) -> None:
    """Content between markers is written verbatim to the output file."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/notes.tex
        \\section{Intro}
        Hello world
        \\end{document}
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert len(result.files) == 1
    text = result.files[0].output_path.read_text()
    assert "\\section{Intro}" in text
    assert "Hello world" in text
    assert "\\end{document}" in text


def test_split_no_markers(tmp_path: Path) -> None:
    """File without markers produces no split files."""
    src = _make_source(
        tmp_path,
        """\
        just some text
        no markers here
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert result.files == ()
    assert result.import_lines == ()


def test_split_creates_parent_dirs(tmp_path: Path) -> None:
    """Nested output paths are created automatically."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/tema01/deep.tex
        content
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert len(result.files) == 1
    assert result.files[0].output_path.exists()


def test_split_skip_existing(tmp_path: Path) -> None:
    """Existing output files are not overwritten when overwrite=False."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/intro.tex
        new content
        """,
    )
    existing = tmp_path / "lect" / "tex" / "intro.tex"
    existing.parent.mkdir(parents=True)
    existing.write_text("original content")

    result = split_notes_file(src, tmp_path, overwrite=False)

    assert len(result.files) == 1
    sf = result.files[0]
    assert sf.created is False
    assert existing.read_text() == "original content"


def test_split_overwrite(tmp_path: Path) -> None:
    """Existing output files ARE overwritten when overwrite=True."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/intro.tex
        new content
        """,
    )
    existing = tmp_path / "lect" / "tex" / "intro.tex"
    existing.parent.mkdir(parents=True)
    existing.write_text("original content")

    result = split_notes_file(src, tmp_path, overwrite=True)

    assert len(result.files) == 1
    sf = result.files[0]
    assert sf.created is True
    assert "new content" in existing.read_text()


def test_split_line_count(tmp_path: Path) -> None:
    """SplitFile.line_count matches lines written."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/a.tex
        line one
        line two
        line three
        """,
    )

    result = split_notes_file(src, tmp_path)

    assert result.files[0].line_count == 3


def test_split_source_path_in_result(tmp_path: Path) -> None:
    """SplitResult.source_path is the absolute source path."""
    src = _make_source(tmp_path, "")
    result = split_notes_file(src, tmp_path)
    assert result.source_path == src.resolve()


def test_split_custom_output_dir(tmp_path: Path) -> None:
    """Output files are placed in output_dir when provided."""
    src = _make_source(
        tmp_path,
        """\
        %>sub/file.tex
        content
        """,
    )
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    result = split_notes_file(src, out_dir)

    assert len(result.files) == 1
    assert result.files[0].output_path.is_relative_to(out_dir)


def test_split_end_marker_no_output_file(tmp_path: Path) -> None:
    """Section started but terminated by END does NOT appear in import_lines."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/real.tex
        content
        %>END
        """,
    )
    result = split_notes_file(src, tmp_path)
    # Only real.tex should be in import_lines
    assert len(result.import_lines) == 1
    assert "real.tex" in result.import_lines[0]


def test_split_multiple_sections_and_end(tmp_path: Path) -> None:
    """Multiple sections with an END in the middle."""
    src = _make_source(
        tmp_path,
        """\
        %>lect/tex/s1.tex
        section one
        %>lect/tex/s2.tex
        section two
        %>END
        after end
        """,
    )
    result = split_notes_file(src, tmp_path)
    assert len(result.files) == 2
    assert len(result.import_lines) == 2


# ── security ─────────────────────────────────────────────────────────────────


def test_split_path_traversal_blocked(tmp_path: Path) -> None:
    """Markers with path traversal are blocked and produce a warning."""
    source = tmp_path / "notes.tex"
    source.write_text("%>../../evil.tex\nevil content\n%>END\n")

    result = split_notes_file(source, tmp_path)

    # The evil file must NOT be created outside tmp_path
    evil_path = (tmp_path / "../../evil.tex").resolve()
    assert not evil_path.exists()
    # A warning about traversal must be present
    assert any(
        "traversal" in w.lower() or "blocked" in w.lower() for w in result.warnings
    )
