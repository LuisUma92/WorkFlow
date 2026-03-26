"""Tests for workflow.lecture.scanner — Phase 5a."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workflow.db.base import LocalBase
from workflow.lecture.scanner import ScanResult, generate_note_reference, register_notes, scan_lecture_directory


# ── DB fixture ───────────────────────────────────────────────────────────────


@pytest.fixture()
def local_session():
    """In-memory SQLite session using LocalBase."""
    engine = create_engine("sqlite:///:memory:")
    LocalBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


# ── scan_lecture_directory ──────────────────────────────────────────────────


def test_scan_finds_tex_files(tmp_path: Path) -> None:
    """scan_lecture_directory returns .tex files inside default subdirs."""
    lect_tex = tmp_path / "lect" / "tex"
    lect_tex.mkdir(parents=True)
    (lect_tex / "intro.tex").write_text("\\section{Intro}")
    (lect_tex / "body.tex").write_text("\\section{Body}")

    found = scan_lecture_directory(tmp_path)

    assert len(found) == 2
    assert all(p.suffix == ".tex" for p in found)
    assert {p.name for p in found} == {"intro.tex", "body.tex"}


def test_scan_ignores_non_tex(tmp_path: Path) -> None:
    """scan_lecture_directory skips non-.tex files."""
    lect_tex = tmp_path / "lect" / "tex"
    lect_tex.mkdir(parents=True)
    (lect_tex / "notes.tex").write_text("")
    (lect_tex / "readme.md").write_text("")
    (lect_tex / "data.yaml").write_text("")

    found = scan_lecture_directory(tmp_path)

    assert len(found) == 1
    assert found[0].name == "notes.tex"


def test_scan_empty_directory(tmp_path: Path) -> None:
    """scan_lecture_directory returns empty list when no .tex files exist."""
    (tmp_path / "lect" / "tex").mkdir(parents=True)
    (tmp_path / "eval" / "tex").mkdir(parents=True)

    found = scan_lecture_directory(tmp_path)

    assert found == []


def test_scan_missing_subdirs(tmp_path: Path) -> None:
    """scan_lecture_directory tolerates missing subdirectories."""
    # No subdirs created at all — should return empty without error
    found = scan_lecture_directory(tmp_path)
    assert found == []


def test_scan_searches_both_default_subdirs(tmp_path: Path) -> None:
    """scan_lecture_directory searches lect/tex and eval/tex."""
    (tmp_path / "lect" / "tex").mkdir(parents=True)
    (tmp_path / "eval" / "tex").mkdir(parents=True)
    (tmp_path / "lect" / "tex" / "a.tex").write_text("")
    (tmp_path / "eval" / "tex" / "b.tex").write_text("")

    found = scan_lecture_directory(tmp_path)

    assert {p.name for p in found} == {"a.tex", "b.tex"}


def test_scan_with_custom_subdirs(tmp_path: Path) -> None:
    """scan_lecture_directory accepts custom subdirs."""
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "c.tex").write_text("")

    found = scan_lecture_directory(tmp_path, subdirs=("notes",))

    assert len(found) == 1
    assert found[0].name == "c.tex"


def test_scan_returns_sorted_paths(tmp_path: Path) -> None:
    """scan_lecture_directory returns sorted paths."""
    lect_tex = tmp_path / "lect" / "tex"
    lect_tex.mkdir(parents=True)
    (lect_tex / "zzz.tex").write_text("")
    (lect_tex / "aaa.tex").write_text("")

    found = scan_lecture_directory(tmp_path)

    assert found == sorted(found)


def test_scan_recurses_nested_dirs(tmp_path: Path) -> None:
    """scan_lecture_directory recurses into nested directories."""
    nested = tmp_path / "lect" / "tex" / "tema01" / "subtema"
    nested.mkdir(parents=True)
    (nested / "deep.tex").write_text("")

    found = scan_lecture_directory(tmp_path)

    assert len(found) == 1
    assert found[0].name == "deep.tex"


# ── generate_note_reference ─────────────────────────────────────────────────


def test_generate_note_reference_flat(tmp_path: Path) -> None:
    """Flat path → single-segment reference."""
    filepath = tmp_path / "lect" / "tex" / "intro.tex"
    ref = generate_note_reference(filepath, tmp_path)
    assert ref == "lect-tex-intro"


def test_generate_note_reference_nested(tmp_path: Path) -> None:
    """Nested path produces dash-separated reference without extension."""
    filepath = tmp_path / "lect" / "tex" / "tema01" / "intro.tex"
    ref = generate_note_reference(filepath, tmp_path)
    assert ref == "lect-tex-tema01-intro"


def test_generate_note_reference_eval(tmp_path: Path) -> None:
    """eval/tex path produces correct reference."""
    filepath = tmp_path / "eval" / "tex" / "quiz01.tex"
    ref = generate_note_reference(filepath, tmp_path)
    assert ref == "eval-tex-quiz01"


def test_generate_note_reference_strips_extension(tmp_path: Path) -> None:
    """Reference never contains the .tex extension."""
    filepath = tmp_path / "lect" / "tex" / "file.tex"
    ref = generate_note_reference(filepath, tmp_path)
    assert ".tex" not in ref
    assert ref == "lect-tex-file"


# ── register_notes ───────────────────────────────────────────────────────────


class TestRegisterNotes:
    def test_register_new_notes(self, local_session, tmp_path: Path) -> None:
        """register_notes creates Note records for new .tex files."""
        lect_dir = tmp_path / "lect" / "tex"
        lect_dir.mkdir(parents=True)
        (lect_dir / "intro.tex").write_text("\\section{Intro}")

        result = register_notes(tmp_path, local_session)

        assert len(result.registered) > 0
        from workflow.db.models.notes import Note
        notes = local_session.query(Note).all()
        assert len(notes) == len(result.registered)

    def test_register_idempotent(self, local_session, tmp_path: Path) -> None:
        """Calling register_notes twice doesn't create duplicates."""
        lect_dir = tmp_path / "lect" / "tex"
        lect_dir.mkdir(parents=True)
        (lect_dir / "intro.tex").write_text("content")

        result1 = register_notes(tmp_path, local_session)
        local_session.commit()
        result2 = register_notes(tmp_path, local_session)

        assert len(result2.registered) == 0
        assert len(result2.already_registered) == len(result1.registered)

    def test_register_returns_scan_result(self, local_session, tmp_path: Path) -> None:
        """register_notes returns a properly formed ScanResult."""
        result = register_notes(tmp_path, local_session)
        assert isinstance(result, ScanResult)

    def test_register_multiple_files(self, local_session, tmp_path: Path) -> None:
        """All .tex files in subdirs are registered."""
        (tmp_path / "lect" / "tex").mkdir(parents=True)
        (tmp_path / "eval" / "tex").mkdir(parents=True)
        (tmp_path / "lect" / "tex" / "a.tex").write_text("a")
        (tmp_path / "lect" / "tex" / "b.tex").write_text("b")
        (tmp_path / "eval" / "tex" / "q.tex").write_text("q")

        result = register_notes(tmp_path, local_session)

        assert len(result.registered) == 3
        assert len(result.discovered) == 3

    def test_register_discovered_equals_registered_on_first_run(
        self, local_session, tmp_path: Path
    ) -> None:
        """On first run with no prior DB entries, discovered == registered."""
        lect_dir = tmp_path / "lect" / "tex"
        lect_dir.mkdir(parents=True)
        (lect_dir / "x.tex").write_text("x")

        result = register_notes(tmp_path, local_session)

        assert set(result.discovered) == set(result.registered)

    def test_register_empty_directory(self, local_session, tmp_path: Path) -> None:
        """register_notes on empty lecture dir returns ScanResult with empty tuples."""
        result = register_notes(tmp_path, local_session)

        assert isinstance(result, ScanResult)
        assert result.registered == ()
        assert result.discovered == ()
