"""Tests for `workflow notes sync --rebuild-edges` (Wave 3 D1)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from workflow.db.models.notes import NoteEdge
from workflow.notes.sync import sync_vault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    content = f"---\n{frontmatter.strip()}\n---\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


def _note_with_edges(vault: Path) -> None:
    """Write two notes: A derives from B (structural continuation edge)."""
    _write_md(
        vault / "noteB.md",
        "id: zettelBBBBBBBB\ntitle: Note B\ntype: permanent",
    )
    _write_md(
        vault / "noteA.md",
        """\
id: zettelAAAAAAAA
title: Note A
type: permanent
relations:
  derived_from:
    - id: zettelBBBBBBBB
      type: continuation
""",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rebuild_drops_removed_edge(tmp_path, global_session):
    """After removing an edge from frontmatter, rebuild_edges=True drops the stale DB row."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Initial sync: A has an edge to B
    _note_with_edges(vault)
    sync_vault(vault, global_session)
    global_session.commit()

    # Verify edge was created
    edges = global_session.scalars(select(NoteEdge)).all()
    assert any(e.target_zettel_id == "zettelBBBBBBBB" for e in edges), \
        "Edge A→B should exist after initial sync"

    # Now rewrite noteA without the edge
    _write_md(
        vault / "noteA.md",
        "id: zettelAAAAAAAA\ntitle: Note A\ntype: permanent",
    )

    # Incremental sync (no flag): edge stays
    sync_vault(vault, global_session)
    global_session.commit()
    edges_after_incremental = global_session.scalars(select(NoteEdge)).all()
    assert any(e.target_zettel_id == "zettelBBBBBBBB" for e in edges_after_incremental), \
        "Without rebuild_edges, stale edge should NOT be dropped by incremental sync"

    # Rebuild sync: edge is dropped
    sync_vault(vault, global_session, rebuild_edges=True)
    global_session.commit()
    edges_after_rebuild = global_session.scalars(select(NoteEdge)).all()
    assert not any(e.target_zettel_id == "zettelBBBBBBBB" for e in edges_after_rebuild), \
        "After rebuild_edges, removed edge should be gone"


def test_incremental_sync_leaves_unrelated_edges_intact(tmp_path, global_session):
    """Incremental sync (no rebuild_edges) does not touch edges from unscoped notes."""
    vault = tmp_path / "vault"
    vault.mkdir()

    _note_with_edges(vault)
    sync_vault(vault, global_session)
    global_session.commit()

    edge_count_before = len(global_session.scalars(select(NoteEdge)).all())
    assert edge_count_before > 0, "Should have at least one edge"

    # Sync again without any changes — edges should remain
    sync_vault(vault, global_session)
    global_session.commit()

    edge_count_after = len(global_session.scalars(select(NoteEdge)).all())
    assert edge_count_after == edge_count_before, \
        "Incremental sync should not drop existing edges"


def test_rebuild_edges_re_upserts_current_edges(tmp_path, global_session):
    """rebuild_edges keeps edges that still exist in frontmatter after rebuild."""
    vault = tmp_path / "vault"
    vault.mkdir()

    _note_with_edges(vault)
    sync_vault(vault, global_session)
    global_session.commit()

    # Rebuild without changing frontmatter → same edge should still exist
    sync_vault(vault, global_session, rebuild_edges=True)
    global_session.commit()

    edges = global_session.scalars(select(NoteEdge)).all()
    assert any(e.target_zettel_id == "zettelBBBBBBBB" for e in edges), \
        "After rebuild with unchanged frontmatter, edge should still exist"


def test_sync_cli_rebuild_edges_flag(tmp_path, monkeypatch):
    """CLI: `notes sync --rebuild-edges` exits 0."""
    from click.testing import CliRunner
    from workflow.notes.cli import notes

    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    _note_with_edges(vault)

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["sync", "--rebuild-edges"],
        env={
            "WORKFLOW_VAULT_ROOT": str(vault),
            "WORKFLOW_DATA_DIR": str(data_dir),
        },
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output


def test_sync_cli_force_flag(tmp_path):
    """CLI: `notes sync --force` is accepted (no-op beyond rebuild)."""
    from click.testing import CliRunner
    from workflow.notes.cli import notes

    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["sync", "--force"],
        env={
            "WORKFLOW_VAULT_ROOT": str(vault),
            "WORKFLOW_DATA_DIR": str(data_dir),
        },
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
