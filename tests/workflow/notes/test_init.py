"""Tests for workflow.notes.init — workspace initialization."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from workflow.notes.init import init_workspace
from workflow.notes.cli import notes


@pytest.fixture
def runner():
    return CliRunner()


class TestInitWorkspace:
    def test_creates_workflow_marker(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / ".workflow" / "config.yaml").exists()

    def test_config_contains_workspace_path(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / ".workflow" / "config.yaml").read_text()
        assert "workspace:" in content
        assert "version: 1" in content

    def test_creates_vault_inbox(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / "00ZZ-Vault" / "inbox").is_dir()

    def test_creates_vault_templates(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / "00ZZ-Vault" / "templates").is_dir()

    def test_creates_note_templates(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / "00ZZ-Vault" / "templates" / "permanent.md").exists()
        assert (tmp_path / "00ZZ-Vault" / "templates" / "literature.md").exists()
        assert (tmp_path / "00ZZ-Vault" / "templates" / "fleeting.md").exists()

    def test_initializes_project_dirs(self, tmp_path):
        (tmp_path / "10MC-ClassicalMechanics").mkdir()
        (tmp_path / "40EM-Electromagnetism").mkdir()
        init_workspace(tmp_path)
        assert (tmp_path / "10MC-ClassicalMechanics" / "notes").is_dir()
        assert (tmp_path / "40EM-Electromagnetism" / "notes").is_dir()

    def test_skips_special_directories(self, tmp_path):
        (tmp_path / "00AA-Lectures").mkdir()
        (tmp_path / "00BB-Bibliography").mkdir()
        (tmp_path / "00EE-ExamplesExercises").mkdir()
        (tmp_path / "00II-Images").mkdir()
        (tmp_path / "00ZZ-Vault").mkdir()
        init_workspace(tmp_path)
        assert not (tmp_path / "00AA-Lectures" / "notes").exists()
        assert not (tmp_path / "00BB-Bibliography" / "notes").exists()
        assert not (tmp_path / "00EE-ExamplesExercises" / "notes").exists()
        assert not (tmp_path / "00II-Images" / "notes").exists()

    def test_skips_non_project_directories(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".workflow").mkdir()
        (tmp_path / "not-a-project").mkdir()
        init_workspace(tmp_path)
        assert not (tmp_path / ".git" / "notes").exists()
        assert not (tmp_path / "not-a-project" / "notes").exists()

    def test_idempotent(self, tmp_path):
        (tmp_path / "10MC-ClassicalMechanics").mkdir()
        init_workspace(tmp_path)
        result2 = init_workspace(tmp_path)
        assert len(result2.directories_created) == 0

    def test_creates_slipbox_db(self, tmp_path):
        (tmp_path / "10MC-ClassicalMechanics").mkdir()
        init_workspace(tmp_path)
        assert (tmp_path / "10MC-ClassicalMechanics" / "slipbox.db").exists()

    def test_result_tracks_created_dirs(self, tmp_path):
        result = init_workspace(tmp_path)
        assert ".workflow/" in result.directories_created
        assert "00ZZ-Vault/" in result.directories_created

    def test_result_tracks_already_existed(self, tmp_path):
        init_workspace(tmp_path)
        result2 = init_workspace(tmp_path)
        assert ".workflow/" in result2.already_existed

    def test_result_tracks_projects_initialized(self, tmp_path):
        (tmp_path / "10MC-ClassicalMechanics").mkdir()
        result = init_workspace(tmp_path)
        assert "10MC-ClassicalMechanics" in result.projects_initialized

    def test_no_duplicate_project_init_on_rerun(self, tmp_path):
        (tmp_path / "10MC-ClassicalMechanics").mkdir()
        init_workspace(tmp_path)
        result2 = init_workspace(tmp_path)
        assert "10MC-ClassicalMechanics" not in result2.projects_initialized

    def test_workspace_dir_stored_in_result(self, tmp_path):
        result = init_workspace(tmp_path)
        assert result.workspace_dir == tmp_path

    def test_handles_files_in_workspace(self, tmp_path):
        (tmp_path / "README.md").write_text("hello")
        result = init_workspace(tmp_path)
        assert result.workspace_dir == tmp_path  # no crash


class TestInitCLI:
    def test_init_command_succeeds(self, runner, tmp_path):
        result = runner.invoke(notes, ["init", str(tmp_path)])
        assert result.exit_code == 0

    def test_init_command_shows_created(self, runner, tmp_path):
        result = runner.invoke(notes, ["init", str(tmp_path)])
        assert "Created" in result.output

    def test_init_nonexistent_path(self, runner):
        result = runner.invoke(notes, ["init", "/nonexistent/path/that/does/not/exist"])
        assert result.exit_code != 0

    def test_init_already_initialized(self, runner, tmp_path):
        runner.invoke(notes, ["init", str(tmp_path)])
        result2 = runner.invoke(notes, ["init", str(tmp_path)])
        assert result2.exit_code == 0
        assert "already initialized" in result2.output

    def test_init_shows_projects(self, runner, tmp_path):
        (tmp_path / "10MC-ClassicalMechanics").mkdir()
        result = runner.invoke(notes, ["init", str(tmp_path)])
        assert "Projects initialized" in result.output
        assert "10MC-ClassicalMechanics" in result.output

    def test_init_default_current_dir(self, runner, tmp_path):
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(notes, ["init"])
            assert result.exit_code == 0
        finally:
            os.chdir(old_cwd)

    def test_notes_group_help(self, runner):
        result = runner.invoke(notes, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
