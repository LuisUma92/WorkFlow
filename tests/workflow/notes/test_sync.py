"""Tests for workflow.notes.sync — sync_vault() public API."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from sqlalchemy import select

from workflow.db.models.notes import Label, Link, Note
from workflow.notes.sync import SyncReport, sync_vault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    """Write a minimal .md file with YAML frontmatter."""
    content = f"---\n{frontmatter.strip()}\n---\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit tests — sync_vault()
# ---------------------------------------------------------------------------


def test_sync_empty_vault_noop(tmp_path, global_session):
    """Empty vault directory produces a zero SyncReport and touches no DB rows."""
    report = sync_vault(tmp_path, global_session)

    assert isinstance(report, SyncReport)
    assert report.notes_scanned == 0
    assert report.labels_registered == 0
    assert report.links_created == 0
    assert report.orphans_dropped == 0


def test_sync_creates_note_rows_from_md(tmp_path, global_session):
    """A .md file with reference: in frontmatter creates a Note row."""
    _write_md(
        tmp_path / "my-note.md",
        "reference: my-note\ntitle: My Note\nnote_type: permanent",
    )

    sync_vault(tmp_path, global_session)

    note = global_session.scalars(
        select(Note).where(Note.reference == "my-note")
    ).first()
    assert note is not None
    assert note.reference == "my-note"


def test_sync_creates_label_rows_from_frontmatter_anchors(tmp_path, global_session):
    """anchors: list in frontmatter creates Label rows (plus synthetic __note__ label)."""
    _write_md(
        tmp_path / "anchored.md",
        textwrap.dedent("""\
            reference: anchored-note
            title: Anchored
            note_type: permanent
            anchors:
              - sec-intro
              - sec-results
        """),
    )

    sync_vault(tmp_path, global_session)

    note = global_session.scalars(
        select(Note).where(Note.reference == "anchored-note")
    ).first()
    assert note is not None

    labels = global_session.scalars(
        select(Label).where(Label.note_id == note.id)
    ).all()
    label_names = {lbl.label for lbl in labels}

    assert "sec-intro" in label_names
    assert "sec-results" in label_names
    assert "__note__" in label_names
    assert len(labels) >= 3


def test_sync_creates_link_rows_from_wikilinks(tmp_path, global_session):
    """[[target-ref]] wikilink in body creates a Link row source→target __note__ label."""
    _write_md(
        tmp_path / "target.md",
        "reference: target-ref\ntitle: Target\nnote_type: permanent",
    )
    _write_md(
        tmp_path / "source.md",
        "reference: source-ref\ntitle: Source\nnote_type: permanent",
        body="See also [[target-ref]] for details.",
    )

    sync_vault(tmp_path, global_session)

    source_note = global_session.scalars(
        select(Note).where(Note.reference == "source-ref")
    ).first()
    target_note = global_session.scalars(
        select(Note).where(Note.reference == "target-ref")
    ).first()
    assert source_note is not None
    assert target_note is not None

    target_label = global_session.scalars(
        select(Label).where(Label.note_id == target_note.id, Label.label == "__note__")
    ).first()
    assert target_label is not None

    link = global_session.scalars(
        select(Link).where(
            Link.source_id == source_note.id, Link.target_id == target_label.id
        )
    ).first()
    assert link is not None


def test_sync_wikilink_with_anchor_targets_named_label(tmp_path, global_session):
    """[[note#sec-results]] wikilink resolves to the named Label, not __note__."""
    _write_md(
        tmp_path / "target.md",
        textwrap.dedent("""\
            reference: target-ref
            title: Target
            note_type: permanent
            anchors:
              - sec-results
        """),
    )
    _write_md(
        tmp_path / "source.md",
        "reference: source-ref\ntitle: Source\nnote_type: permanent",
        body="See [[target-ref#sec-results]] for details.",
    )

    sync_vault(tmp_path, global_session)

    source_note = global_session.scalars(
        select(Note).where(Note.reference == "source-ref")
    ).first()
    target_note = global_session.scalars(
        select(Note).where(Note.reference == "target-ref")
    ).first()
    anchor_label = global_session.scalars(
        select(Label).where(
            Label.note_id == target_note.id, Label.label == "sec-results"
        )
    ).first()
    assert anchor_label is not None

    link = global_session.scalars(
        select(Link).where(
            Link.source_id == source_note.id, Link.target_id == anchor_label.id
        )
    ).first()
    assert link is not None


def test_sync_wikilink_with_display_text_creates_link(tmp_path, global_session):
    """[[note|display text]] form creates a Link (display text is ignored)."""
    _write_md(
        tmp_path / "target.md",
        "reference: target-ref\ntitle: Target\nnote_type: permanent",
    )
    _write_md(
        tmp_path / "source.md",
        "reference: source-ref\ntitle: Source\nnote_type: permanent",
        body="See [[target-ref|the target note]] here.",
    )

    sync_vault(tmp_path, global_session)

    source_note = global_session.scalars(
        select(Note).where(Note.reference == "source-ref")
    ).first()
    target_note = global_session.scalars(
        select(Note).where(Note.reference == "target-ref")
    ).first()
    target_label = global_session.scalars(
        select(Label).where(Label.note_id == target_note.id, Label.label == "__note__")
    ).first()

    link = global_session.scalars(
        select(Link).where(
            Link.source_id == source_note.id, Link.target_id == target_label.id
        )
    ).first()
    assert link is not None


def test_sync_wikilink_to_missing_target_skipped(tmp_path, global_session):
    """[[missing-ref]] wikilink silently skips when target is not in the vault."""
    _write_md(
        tmp_path / "source.md",
        "reference: source-ref\ntitle: Source\nnote_type: permanent",
        body="See [[does-not-exist]] for details.",
    )

    report = sync_vault(tmp_path, global_session)

    assert report.links_created == 0
    assert global_session.scalars(select(Link)).all() == []


def test_sync_idempotent_second_run_no_changes(tmp_path, global_session):
    """Running sync twice does not create duplicate Label or Link rows."""
    _write_md(
        tmp_path / "target.md",
        "reference: target-ref\ntitle: Target\nnote_type: permanent",
    )
    _write_md(
        tmp_path / "source.md",
        "reference: source-ref\ntitle: Source\nnote_type: permanent",
        body="See [[target-ref]].",
    )

    sync_vault(tmp_path, global_session)
    report2 = sync_vault(tmp_path, global_session)

    assert report2.labels_registered == 0
    assert report2.links_created == 0


def test_sync_dry_run_writes_nothing(tmp_path, global_session):
    """dry_run=True parses files but writes no rows to the DB."""
    _write_md(
        tmp_path / "note.md",
        "reference: dry-note\ntitle: Dry\nnote_type: permanent",
        body="Body with [[other-ref]].",
    )

    sync_vault(tmp_path, global_session, dry_run=True)

    assert global_session.scalars(select(Note)).all() == []
    assert global_session.scalars(select(Label)).all() == []
    assert global_session.scalars(select(Link)).all() == []


def test_sync_orphan_link_dropped_and_reported(tmp_path, global_session):
    """Deleting the source file and re-syncing drops orphaned Link rows."""
    _write_md(
        tmp_path / "target.md",
        "reference: target-ref\ntitle: Target\nnote_type: permanent",
    )
    source_md = _write_md(
        tmp_path / "source.md",
        "reference: source-ref\ntitle: Source\nnote_type: permanent",
        body="See [[target-ref]].",
    )

    sync_vault(tmp_path, global_session)
    assert global_session.scalars(select(Link)).all() != []

    source_md.unlink()

    report2 = sync_vault(tmp_path, global_session)

    assert report2.orphans_dropped >= 1
    assert global_session.scalars(select(Link)).all() == []


def test_sync_project_filter_scopes_to_subtree(tmp_path, global_session):
    """project_filter restricts sync to a named subdirectory."""
    proj1 = tmp_path / "0001AA-proj1"
    proj2 = tmp_path / "0002BB-proj2"
    proj1.mkdir()
    proj2.mkdir()

    _write_md(
        proj1 / "note-a.md",
        "reference: proj1-note\ntitle: Proj1 Note\nnote_type: permanent",
    )
    _write_md(
        proj2 / "note-b.md",
        "reference: proj2-note\ntitle: Proj2 Note\nnote_type: permanent",
    )

    sync_vault(tmp_path, global_session, project_filter="0001AA-proj1")

    assert global_session.scalars(
        select(Note).where(Note.reference == "proj1-note")
    ).first() is not None
    assert global_session.scalars(
        select(Note).where(Note.reference == "proj2-note")
    ).first() is None


def test_sync_path_traversal_in_frontmatter_blocked(tmp_path, global_session):
    """Malicious anchor paths (../../etc/passwd) are rejected — not written to DB."""
    _write_md(
        tmp_path / "malicious.md",
        textwrap.dedent("""\
            reference: malicious-note
            title: Evil
            note_type: permanent
            anchors:
              - ../../etc/passwd
              - normal-anchor
        """),
    )

    sync_vault(tmp_path, global_session)

    labels = global_session.scalars(select(Label)).all()
    label_names = {lbl.label for lbl in labels}

    assert "../../etc/passwd" not in label_names


def test_sync_project_filter_traversal_blocked(tmp_path, global_session):
    """project_filter with traversal path raises ValueError."""
    with pytest.raises(ValueError, match="escapes vault_root"):
        sync_vault(tmp_path, global_session, project_filter="../../etc")
