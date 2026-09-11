"""Characterization tests for split_notes_file — pinning behaviour before refactor.

These tests capture behaviour of ``split_notes_file`` that was not already
covered by ``tests/workflow/lecture/test_note_splitter.py``, so the refactor
extracting private helpers cannot silently change it.

The path-traversal security invariant (marker paths must stay contained
within ``output_dir``) is already covered by
``tests/workflow/lecture/test_note_splitter.py::test_split_path_traversal_blocked``
and is not duplicated here.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from workflow.lecture.note_splitter import split_notes_file


def _make_source(tmp_path: Path, content: str, name: str = "notes.tex") -> Path:
    src = tmp_path / name
    src.write_text(dedent(content))
    return src


def test_split_default_output_dir_is_source_parent(tmp_path: Path) -> None:
    """When output_dir is omitted, markers resolve relative to source_path.parent."""
    src = _make_source(
        tmp_path,
        """\
        %>sub/generated.tex
        content
        """,
    )

    result = split_notes_file(src)

    assert len(result.files) == 1
    expected = (tmp_path / "sub" / "generated.tex").resolve()
    assert result.files[0].output_path == expected
    assert expected.exists()
