"""Tests for workflow.vault.cli — ITEP-0011 P2.3."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from workflow.vault.cli import vault


def _make_vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("permanent", "literature", "fleeting"):
        (root / "notes" / sub).mkdir(parents=True)
    return root


def _make_project_with_note(tmp_path: Path, ref: str = "ref-1") -> Path:
    project = tmp_path / "01PHTH-2503-thesis"
    project.mkdir()
    db_path = project / "slipbox.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE note (
            id INTEGER PRIMARY KEY, filename TEXT UNIQUE, reference TEXT UNIQUE,
            last_build_date_html TEXT, last_build_date_pdf TEXT,
            last_edit_date TEXT, created TEXT,
            title TEXT, note_type TEXT, source_format TEXT, zettel_id TEXT
        );
        CREATE TABLE citation (id INTEGER PRIMARY KEY, note_id INT, citationkey TEXT);
        CREATE TABLE label (id INTEGER PRIMARY KEY, note_id INT, label TEXT);
        CREATE TABLE link (id INTEGER PRIMARY KEY, source_id INT, target_id INT);
        CREATE TABLE tag (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
        CREATE TABLE note_tag (note_id INT, tag_id INT);
        """
    )
    conn.execute(
        "INSERT INTO note (id, filename, reference, note_type, source_format) "
        "VALUES (1, 'n.md', ?, 'permanent', 'md')",
        (ref,),
    )
    conn.commit()
    conn.close()
    return project


@pytest.fixture()
def isolated_global_db(tmp_path, monkeypatch):
    """Point GlobalBase engine at an in-tree path so tests don't touch user DB."""
    data = tmp_path / "share" / "workflow"
    data.mkdir(parents=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(_make_vault(tmp_path)))
    return tmp_path


def test_info(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(_make_vault(tmp_path)))
    result = CliRunner().invoke(vault, ["info"])
    assert result.exit_code == 0, result.output
    assert "vault_root" in result.output
    assert "permanent" in result.output


def test_validate_ok(monkeypatch, tmp_path):
    root = _make_vault(tmp_path)
    monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(root))
    result = CliRunner().invoke(vault, ["validate"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_missing(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    (root / "notes" / "permanent").mkdir(parents=True)
    monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(root))
    result = CliRunner().invoke(vault, ["validate"])
    assert result.exit_code != 0
    assert "literature" in result.output


def test_unify_dry_run(isolated_global_db, tmp_path):
    project = _make_project_with_note(tmp_path)
    result = CliRunner().invoke(
        vault,
        ["unify", "--project-root", str(project), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "notes:     1" in result.output
    assert not (project / ".vault_pointer").exists()


def test_unify_no_dry_run_writes(isolated_global_db, tmp_path):
    project = _make_project_with_note(tmp_path)
    backup = tmp_path / "backups"
    result = CliRunner().invoke(
        vault,
        [
            "unify",
            "--project-root",
            str(project),
            "--backup-dir",
            str(backup),
            "--no-dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (project / ".vault_pointer").exists()
    assert any(backup.iterdir())


def test_unify_manual_collision_exits_nonzero(isolated_global_db, tmp_path):
    """Post-review: skipped collisions must surface as a non-zero exit even
    when --rename-strategy is not 'abort'."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import init_global_db
    from workflow.db.models.notes import Note

    project = _make_project_with_note(tmp_path, ref="ref-clash")
    engine = init_global_db()
    with Session(engine) as s:
        s.add(Note(filename="pre.md", reference="ref-clash"))
        s.commit()

    backup = tmp_path / "backups"
    result = CliRunner().invoke(
        vault,
        [
            "unify",
            "--project-root",
            str(project),
            "--backup-dir",
            str(backup),
            "--rename-strategy",
            "manual",
            "--no-dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "ref-clash" in result.output
