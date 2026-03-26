"""Tests for workflow.lecture.cli — Click commands."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from workflow.lecture.cli import lectures


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── scan command ────────────────────────────────────────────────────────────


def test_scan_command_finds_tex_files(runner: CliRunner, tmp_path: Path) -> None:
    """scan command reports discovered .tex files."""
    lect_tex = tmp_path / "lect" / "tex"
    lect_tex.mkdir(parents=True)
    (lect_tex / "intro.tex").write_text("content")

    result = runner.invoke(lectures, ["scan", str(tmp_path), "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "intro.tex" in result.output or "1" in result.output


def test_scan_empty_dir_message(runner: CliRunner, tmp_path: Path) -> None:
    """scan command reports nothing found when directory is empty."""
    result = runner.invoke(lectures, ["scan", str(tmp_path), "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    # Should indicate nothing was discovered
    assert "0" in result.output or "No" in result.output or "no" in result.output


def test_scan_registers_notes_in_db(runner: CliRunner, tmp_path: Path) -> None:
    """scan command registers found .tex files in the local slipbox.db."""
    lect_tex = tmp_path / "lect" / "tex"
    lect_tex.mkdir(parents=True)
    (lect_tex / "topic.tex").write_text("\\section{Topic}")

    result = runner.invoke(lectures, ["scan", str(tmp_path), "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    # DB file should have been created
    db_path = tmp_path / "slipbox.db"
    assert db_path.exists()


# ── split command ────────────────────────────────────────────────────────────


def test_split_command_basic(runner: CliRunner, tmp_path: Path) -> None:
    """split command splits a notes file and reports output files."""
    src = tmp_path / "notes.tex"
    src.write_text(dedent("""\
        %>lect/tex/intro.tex
        content here
        %>lect/tex/body.tex
        more content
    """))

    result = runner.invoke(
        lectures,
        ["split", str(src), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "lect" / "tex" / "intro.tex").exists()
    assert (tmp_path / "lect" / "tex" / "body.tex").exists()


def test_split_command_no_markers(runner: CliRunner, tmp_path: Path) -> None:
    """split command reports no files when source has no markers."""
    src = tmp_path / "notes.tex"
    src.write_text("just text, no markers\n")

    result = runner.invoke(
        lectures,
        ["split", str(src), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "0" in result.output or "No" in result.output or "no" in result.output


def test_split_command_overwrite_flag(runner: CliRunner, tmp_path: Path) -> None:
    """--overwrite flag causes existing files to be replaced."""
    src = tmp_path / "notes.tex"
    src.write_text(dedent("""\
        %>lect/tex/intro.tex
        new content
    """))
    existing = tmp_path / "lect" / "tex" / "intro.tex"
    existing.parent.mkdir(parents=True)
    existing.write_text("old content")

    result = runner.invoke(
        lectures,
        ["split", str(src), "--output-dir", str(tmp_path), "--overwrite"],
    )

    assert result.exit_code == 0, result.output
    assert "new content" in existing.read_text()


def test_split_command_default_output_dir(runner: CliRunner, tmp_path: Path) -> None:
    """split command uses source file's directory when --output-dir is omitted."""
    src = tmp_path / "notes.tex"
    src.write_text(dedent("""\
        %>lect/tex/file.tex
        text
    """))

    result = runner.invoke(lectures, ["split", str(src)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "lect" / "tex" / "file.tex").exists()


# ── link command ─────────────────────────────────────────────────────────────


def test_link_command_empty_dir(runner: CliRunner, tmp_path: Path) -> None:
    """link command runs without error when no .tex files are found."""
    result = runner.invoke(lectures, ["link", str(tmp_path), "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "References found" in result.output


def test_link_command_processes_tex_files(runner: CliRunner, tmp_path: Path) -> None:
    """link command scans lecture dir and reports citation counts."""
    lect_tex = tmp_path / "lect" / "tex"
    lect_tex.mkdir(parents=True)
    tex = lect_tex / "intro.tex"
    tex.write_text(r"\cite{serway2019} and \label{sec:intro}")

    # Register notes first
    runner.invoke(lectures, ["scan", str(tmp_path), "--project-root", str(tmp_path)])

    result = runner.invoke(lectures, ["link", str(tmp_path), "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Citations found" in result.output


def test_link_command_creates_slipbox_db(runner: CliRunner, tmp_path: Path) -> None:
    """link command initialises slipbox.db when it does not yet exist."""
    result = runner.invoke(lectures, ["link", str(tmp_path), "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    db_path = tmp_path / "slipbox.db"
    assert db_path.exists()


# ── build-eval command ───────────────────────────────────────────────────────


def test_build_eval_help(runner: CliRunner) -> None:
    """build-eval command is registered and shows help."""
    result = runner.invoke(lectures, ["build-eval", "--help"])
    assert result.exit_code == 0, result.output
    assert "build-eval" in result.output or "taxonomy" in result.output.lower()


def test_build_eval_requires_taxonomy_level(runner: CliRunner) -> None:
    """build-eval command requires at least one --taxonomy-level."""
    result = runner.invoke(lectures, ["build-eval"])
    assert result.exit_code != 0


def test_build_eval_with_empty_bank(runner: CliRunner, tmp_path: Path) -> None:
    """build-eval with no matching exercises reports 0 exercises selected."""
    result = runner.invoke(
        lectures,
        [
            "build-eval",
            "--taxonomy-level", "Recordar",
            "--taxonomy-domain", "Información",
            "--count", "3",
            "--points", "5.0",
            "--title", "Test Exam",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Test Exam" in result.output or "0" in result.output


def test_build_eval_outputs_to_file(runner: CliRunner, tmp_path: Path) -> None:
    """build-eval writes output to specified file when --output is given."""
    out_file = tmp_path / "exam.tex"
    result = runner.invoke(
        lectures,
        [
            "build-eval",
            "--taxonomy-level", "Recordar",
            "--count", "1",
            "--points", "10.0",
            "--output", str(out_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_file.exists()


def test_build_eval_moodle_flag(runner: CliRunner, tmp_path: Path) -> None:
    """build-eval --moodle flag produces a .xml file alongside output."""
    out_file = tmp_path / "exam.tex"
    result = runner.invoke(
        lectures,
        [
            "build-eval",
            "--taxonomy-level", "Recordar",
            "--count", "1",
            "--points", "10.0",
            "--output", str(out_file),
            "--moodle",
        ],
    )
    assert result.exit_code == 0, result.output
    xml_file = out_file.with_suffix(".xml")
    assert xml_file.exists()
