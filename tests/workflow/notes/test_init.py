"""Tests for workflow.notes.init — workspace initialization (single-vault model)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from workflow.notes.init import init_workspace, VAULT_NAME
from workflow.notes.cli import notes


@pytest.fixture
def runner():
    return CliRunner()


class TestInitWorkspace:
    def test_creates_workflow_marker(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / ".workflow" / "config.yaml").exists()

    def test_config_contains_workspace_and_vault(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / ".workflow" / "config.yaml").read_text()
        assert "workspace:" in content
        assert f"vault: {VAULT_NAME}" in content
        assert "version: 2" in content

    def test_creates_vault_inbox(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / VAULT_NAME / "inbox").is_dir()

    def test_creates_vault_templates(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / VAULT_NAME / "templates").is_dir()

    def test_creates_note_templates(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / VAULT_NAME / "templates" / "permanent.md").exists()
        assert (tmp_path / VAULT_NAME / "templates" / "literature.md").exists()
        assert (tmp_path / VAULT_NAME / "templates" / "fleeting.md").exists()

    def test_creates_single_slipbox_at_root(self, tmp_path):
        init_workspace(tmp_path)
        assert (tmp_path / "slipbox.db").exists()

    def test_no_per_project_notes_dirs(self, tmp_path):
        """Single-vault model: projects don't get notes/ subdirectories."""
        (tmp_path / "0010MC-ClassicalMechanics").mkdir()
        (tmp_path / "0040EM-Electromagnetism").mkdir()
        init_workspace(tmp_path)
        assert not (tmp_path / "0010MC-ClassicalMechanics" / "notes").exists()
        assert not (tmp_path / "0040EM-Electromagnetism" / "notes").exists()

    def test_no_per_project_slipbox(self, tmp_path):
        """Single-vault model: projects don't get their own slipbox.db."""
        (tmp_path / "0010MC-ClassicalMechanics").mkdir()
        init_workspace(tmp_path)
        assert not (tmp_path / "0010MC-ClassicalMechanics" / "slipbox.db").exists()

    def test_idempotent(self, tmp_path):
        init_workspace(tmp_path)
        result2 = init_workspace(tmp_path)
        assert len(result2.directories_created) == 0

    def test_result_tracks_created_dirs(self, tmp_path):
        result = init_workspace(tmp_path)
        assert ".workflow/" in result.directories_created
        assert f"{VAULT_NAME}/" in result.directories_created
        assert "slipbox.db" in result.directories_created

    def test_result_tracks_already_existed(self, tmp_path):
        init_workspace(tmp_path)
        result2 = init_workspace(tmp_path)
        assert ".workflow/" in result2.already_existed
        assert "slipbox.db" in result2.already_existed

    def test_workspace_dir_stored_in_result(self, tmp_path):
        result = init_workspace(tmp_path)
        assert result.workspace_dir == tmp_path

    def test_handles_files_in_workspace(self, tmp_path):
        (tmp_path / "README.md").write_text("hello")
        result = init_workspace(tmp_path)
        assert result.workspace_dir == tmp_path  # no crash

    def test_permanent_template_has_all_fields(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "permanent.md").read_text()
        assert "exercises: []" in content
        assert "images: []" in content
        assert "references: []" in content

    def test_literature_template_has_bib_fence(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "literature.md").read_text()
        assert "```bib" in content
        assert ":WorkflowBibImport" in content

    def test_fleeting_template_has_no_bib_fence(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "fleeting.md").read_text()
        assert "```bib" not in content

    def test_permanent_template_has_no_bib_fence(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "permanent.md").read_text()
        assert "```bib" not in content

    # Phase 2 — template gap additions

    def test_permanent_template_has_main_topic_and_discipline_area(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "permanent.md").read_text()
        assert "main_topic:" in content
        assert "discipline_area:" in content

    def test_permanent_template_has_relations_scaffold(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "permanent.md").read_text()
        assert "relations:" in content
        assert "derived_from:" in content
        assert "links:" in content
        assert "entry_point:" in content

    def test_permanent_template_no_delivered_from(self, tmp_path):
        """Lock against obsidian.lua delivered_from bug leaking into init templates."""
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "permanent.md").read_text()
        assert "delivered_from" not in content

    def test_literature_template_has_main_topic_discipline_origin(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "literature.md").read_text()
        assert "main_topic:" in content
        assert "discipline_area:" in content
        assert "origin:" in content

    def test_literature_template_has_relations_scaffold(self, tmp_path):
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "literature.md").read_text()
        assert "relations:" in content
        assert "derived_from:" in content
        assert "entry_point:" in content

    def test_fleeting_template_has_no_main_topic(self, tmp_path):
        """Fleeting notes stay minimal — no main_topic or relations."""
        init_workspace(tmp_path)
        content = (tmp_path / VAULT_NAME / "templates" / "fleeting.md").read_text()
        assert "main_topic" not in content
        assert "relations" not in content

    def test_permanent_template_passes_validator(self, tmp_path):
        import yaml
        from workflow.validation.schemas import validate_note_frontmatter
        init_workspace(tmp_path)
        raw = (tmp_path / VAULT_NAME / "templates" / "permanent.md").read_text()
        # Extract frontmatter between --- delimiters
        parts = raw.split("---")
        fm_data = yaml.safe_load(parts[1])
        # Inject required fields that templates leave blank
        fm_data["id"] = "testid123456"
        fm_data["title"] = "Test"
        _, errors = validate_note_frontmatter(fm_data)
        assert errors == []

    def test_literature_template_passes_validator(self, tmp_path):
        import yaml
        from workflow.validation.schemas import validate_note_frontmatter
        init_workspace(tmp_path)
        raw = (tmp_path / VAULT_NAME / "templates" / "literature.md").read_text()
        parts = raw.split("---")
        fm_data = yaml.safe_load(parts[1])
        fm_data["id"] = "litid1234567"
        fm_data["title"] = "Test lit"
        _, errors = validate_note_frontmatter(fm_data)
        assert errors == []


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
