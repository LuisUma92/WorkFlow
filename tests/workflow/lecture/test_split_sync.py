"""Tests for `workflow lectures split --sync/--no-sync` (Wave 0 D1).

Per tasks/plans/2026-07-05-wave0-harvest-loop-plan.md Phase 1: split gains a
--sync/--no-sync flag (default --sync) so newly split notes are indexed
immediately via sync_note_files(), without touching sync_vault's directory-wide
behavior.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.lecture.cli import lectures


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    """Redirect appdirs user_data_dir into tmp so tests don't touch real DB."""
    base = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _source_with_two_notes(tmp_path: Path) -> Path:
    src = tmp_path / "monolith.tex"
    src.write_text(
        dedent("""\
        %>notes/target.md
        ---
        id: target-note
        title: Target
        type: fleeting
        ---
        Target body.
        %>notes/source.md
        ---
        id: source-note
        title: Source
        type: fleeting
        relations:
          derived_from:
            - id: target-note
              type: continuation
        ---
        Source body referencing [[target-note]].
        """)
    )
    return src


def test_split_sync_default_creates_db_rows(runner: CliRunner, tmp_path: Path) -> None:
    """split (default --sync) indexes the newly split notes into the global DB."""
    src = _source_with_two_notes(tmp_path)

    result = runner.invoke(
        lectures, ["split", str(src), "--output-dir", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output

    from workflow.db.engine import init_global_db
    from workflow.db.models.notes import Note, NoteEdge

    engine = init_global_db()
    with Session(engine) as session:
        notes = session.scalars(select(Note)).all()
        zettel_ids = {n.zettel_id for n in notes}
        assert {"target-note", "source-note"} <= zettel_ids

        edges = session.scalars(select(NoteEdge)).all()
        assert len(edges) == 1


def test_split_no_sync_creates_no_db_rows(runner: CliRunner, tmp_path: Path) -> None:
    """--no-sync restores pre-D1 behavior: files are split, zero DB rows created."""
    src = _source_with_two_notes(tmp_path)

    result = runner.invoke(
        lectures,
        ["split", str(src), "--output-dir", str(tmp_path), "--no-sync"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "notes" / "target.md").exists()
    assert (tmp_path / "notes" / "source.md").exists()

    from workflow.db.engine import init_global_db
    from workflow.db.models.notes import Note

    engine = init_global_db()
    with Session(engine) as session:
        notes = session.scalars(select(Note)).all()
        assert notes == []


def test_split_no_sync_stdout_matches_pre_d1_format(
    runner: CliRunner, tmp_path: Path
) -> None:
    """--no-sync output is byte-identical in shape to the pre-D1 split report."""
    src = tmp_path / "notes.tex"
    src.write_text(
        dedent("""\
        %>lect/tex/intro.tex
        content here
        %>lect/tex/body.tex
        more content
    """)
    )

    result = runner.invoke(
        lectures,
        ["split", str(src), "--output-dir", str(tmp_path), "--no-sync"],
    )

    assert result.exit_code == 0, result.output
    assert "Source:" in result.output
    assert "Split files: 2" in result.output
    assert "Created: 2" in result.output
    assert "Synced" not in result.output


def test_split_sync_twice_no_duplicate_rows(runner: CliRunner, tmp_path: Path) -> None:
    """Re-running split --sync (no --overwrite, files already exist) does not
    create duplicate rows — idempotency at the CLI level."""
    src = _source_with_two_notes(tmp_path)

    result1 = runner.invoke(
        lectures, ["split", str(src), "--output-dir", str(tmp_path)]
    )
    assert result1.exit_code == 0, result1.output

    result2 = runner.invoke(
        lectures, ["split", str(src), "--output-dir", str(tmp_path)]
    )
    assert result2.exit_code == 0, result2.output

    from workflow.db.engine import init_global_db
    from workflow.db.models.notes import Note, NoteEdge

    engine = init_global_db()
    with Session(engine) as session:
        notes = session.scalars(select(Note)).all()
        assert len(notes) == 2
        edges = session.scalars(select(NoteEdge)).all()
        assert len(edges) == 1
