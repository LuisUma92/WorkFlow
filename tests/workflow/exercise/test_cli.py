"""Tests for workflow.exercise.cli — exercise CLI commands."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.exercises import Exercise, ExerciseOption
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.cli import exercise


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def runner():
    return CliRunner()


COMPLETE_TEX = """\
% ---
% id: cli-test-001
% type: multichoice
% difficulty: medium
% taxonomy_level: Usar-Aplicar
% taxonomy_domain: Procedimiento Mental
% tags: [physics, electrostatics]
% status: complete
% ---
\\question{
  Find $\\vec{E}$.
  \\begin{enumerate}[a)]
    \\qpart{\\rightoption Option A}{Sol A}
    \\qpart{Option B}{Sol B}
  \\end{enumerate}
}{
  General solution.
}
"""

PLACEHOLDER_TEX = """\
% ---
% id: cli-test-002
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% ---
\\question{...}{
}
"""

NO_METADATA_TEX = """\
\\question{What is $2+2$?}{$4$}
"""


# ── Parse command ────────────────────────────────────────────────────────


class TestParseCommand:
    def test_parse_single_file(self, runner, tmp_path):
        tex_file = tmp_path / "ex001.tex"
        tex_file.write_text(COMPLETE_TEX)

        result = runner.invoke(exercise, ["parse", str(tex_file)])
        assert result.exit_code == 0
        assert "cli-test-001" in result.output
        assert "complete" in result.output

    def test_parse_directory(self, runner, tmp_path):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        (tmp_path / "ex002.tex").write_text(PLACEHOLDER_TEX)

        result = runner.invoke(exercise, ["parse", str(tmp_path)])
        assert result.exit_code == 0
        assert "cli-test-001" in result.output
        assert "cli-test-002" in result.output

    def test_parse_file_without_metadata(self, runner, tmp_path):
        tex_file = tmp_path / "no_meta.tex"
        tex_file.write_text(NO_METADATA_TEX)

        result = runner.invoke(exercise, ["parse", str(tex_file)])
        assert result.exit_code == 0
        assert "WARN" in result.output or "warning" in result.output.lower()

    def test_parse_nonexistent_path(self, runner):
        result = runner.invoke(exercise, ["parse", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_parse_shows_options(self, runner, tmp_path):
        tex_file = tmp_path / "ex001.tex"
        tex_file.write_text(COMPLETE_TEX)

        result = runner.invoke(exercise, ["parse", str(tex_file)])
        assert "2 options" in result.output or "options: 2" in result.output.lower()

    def test_parse_errors_exit_nonzero(self, runner, tmp_path):
        """Files with parse errors cause non-zero exit."""
        bad_file = tmp_path / "bad.tex"
        bad_file.write_text("This has no \\question macro at all.")

        result = runner.invoke(exercise, ["parse", str(bad_file)])
        assert result.exit_code != 0

    def test_parse_non_tex_file(self, runner, tmp_path):
        """Non-.tex file shows no files found."""
        md_file = tmp_path / "notes.md"
        md_file.write_text("# Just markdown")

        result = runner.invoke(exercise, ["parse", str(md_file)])
        assert result.exit_code == 0
        assert "No .tex files" in result.output


# ── Sync command ─────────────────────────────────────────────────────────


class TestSyncCommand:
    def test_sync_creates_records(self, runner, tmp_path, db_engine):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        (tmp_path / "ex002.tex").write_text(PLACEHOLDER_TEX)

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path)],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "2 new" in result.output or "new: 2" in result.output.lower()

        # Verify records exist in DB
        with Session(db_engine) as session:
            repo = SqlExerciseRepo(session)
            assert repo.get_by_exercise_id("cli-test-001") is not None
            assert repo.get_by_exercise_id("cli-test-002") is not None

    def test_sync_updates_changed_file(self, runner, tmp_path, db_engine):
        tex_file = tmp_path / "ex001.tex"
        tex_file.write_text(COMPLETE_TEX)

        # First sync
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        # Modify file
        tex_file.write_text(COMPLETE_TEX.replace("medium", "hard"))

        # Second sync
        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path)],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "1 updated" in result.output or "updated: 1" in result.output.lower()

    def test_sync_skips_unchanged_file(self, runner, tmp_path, db_engine):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)

        # First sync
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        # Second sync (no changes)
        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path)],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "0 new" in result.output or "unchanged" in result.output.lower()

    def test_sync_skips_files_without_metadata(self, runner, tmp_path, db_engine):
        (tmp_path / "no_meta.tex").write_text(NO_METADATA_TEX)

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path)],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        # File without metadata should be skipped (warned, not synced)
        with Session(db_engine) as session:
            repo = SqlExerciseRepo(session)
            assert len(repo.list_all()) == 0

    def test_sync_persists_options(self, runner, tmp_path, db_engine):
        """Sync persists ExerciseOption records for multichoice exercises."""
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        with Session(db_engine) as session:
            repo = SqlExerciseRepo(session)
            ex = repo.get_by_exercise_id("cli-test-001")
            assert ex is not None
            assert ex.option_count == 2
            assert len(ex.options) == 2
            correct = [o for o in ex.options if o.is_correct]
            assert len(correct) == 1
            assert correct[0].label == "a"

    def test_sync_skips_on_parse_error(self, runner, tmp_path, db_engine):
        """Files with parse errors are skipped during sync."""
        bad_file = tmp_path / "bad.tex"
        bad_file.write_text("No question macro here.")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path)],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "SKIP" in result.output


# ── List command ─────────────────────────────────────────────────────────


class TestListCommand:
    def test_list_empty_db(self, runner, db_engine):
        result = runner.invoke(exercise, ["list"], obj={"engine": db_engine})
        assert result.exit_code == 0
        assert "No exercises" in result.output or "0" in result.output

    def test_list_shows_exercises(self, runner, tmp_path, db_engine):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        result = runner.invoke(exercise, ["list"], obj={"engine": db_engine})
        assert result.exit_code == 0
        assert "cli-test-001" in result.output

    def test_list_filter_by_status(self, runner, tmp_path, db_engine):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        (tmp_path / "ex002.tex").write_text(PLACEHOLDER_TEX)
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        result = runner.invoke(
            exercise,
            ["list", "--status", "complete"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "cli-test-001" in result.output
        assert "cli-test-002" not in result.output

    def test_list_filter_by_difficulty(self, runner, tmp_path, db_engine):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        result = runner.invoke(
            exercise,
            ["list", "--difficulty", "medium"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "cli-test-001" in result.output

    def test_list_filter_by_type(self, runner, tmp_path, db_engine):
        (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
        (tmp_path / "ex002.tex").write_text(PLACEHOLDER_TEX)
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        result = runner.invoke(
            exercise,
            ["list", "--type", "multichoice"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "cli-test-001" in result.output
        assert "cli-test-002" not in result.output


# ── GC command ───────────────────────────────────────────────────────────


class TestGcCommand:
    def test_gc_removes_orphans(self, runner, tmp_path, db_engine):
        tex_file = tmp_path / "ex001.tex"
        tex_file.write_text(COMPLETE_TEX)

        # Sync to create record
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        # Delete the file
        tex_file.unlink()

        # Run GC with --yes to skip confirmation
        result = runner.invoke(
            exercise,
            ["gc", "--yes"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "Removed 1" in result.output

        # Verify record is gone
        with Session(db_engine) as session:
            repo = SqlExerciseRepo(session)
            assert repo.get_by_exercise_id("cli-test-001") is None

    def test_gc_no_orphans(self, runner, tmp_path, db_engine):
        tex_file = tmp_path / "ex001.tex"
        tex_file.write_text(COMPLETE_TEX)

        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})

        result = runner.invoke(
            exercise,
            ["gc", "--yes"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0
        assert "No orphan" in result.output or "0" in result.output

    def test_gc_confirm_abort(self, runner, tmp_path, db_engine):
        """GC without --yes prompts and can be aborted."""
        tex_file = tmp_path / "ex001.tex"
        tex_file.write_text(COMPLETE_TEX)
        runner.invoke(exercise, ["sync", str(tmp_path)], obj={"engine": db_engine})
        tex_file.unlink()

        # Send 'n' to abort
        result = runner.invoke(
            exercise,
            ["gc"],
            obj={"engine": db_engine},
            input="n\n",
        )
        # Should abort — record still exists
        with Session(db_engine) as session:
            repo = SqlExerciseRepo(session)
            assert repo.get_by_exercise_id("cli-test-001") is not None
