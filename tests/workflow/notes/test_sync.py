"""Tests for workflow.notes.sync — sync_vault() public API."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from sqlalchemy import select

from workflow.db.models.notes import Citation, Label, Link, Note
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
    """A .md file with id: in frontmatter creates a Note row."""
    _write_md(
        tmp_path / "my-note.md",
        "id: my-note\ntitle: My Note\ntype: permanent",
    )

    sync_vault(tmp_path, global_session)

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "my-note")
    ).first()
    assert note is not None
    assert note.zettel_id == "my-note"
    assert note.reference == "my-note"  # legacy column kept in sync


def test_sync_creates_label_rows_from_frontmatter_anchors(tmp_path, global_session):
    """anchors: list in frontmatter creates Label rows (plus synthetic __note__ label)."""
    _write_md(
        tmp_path / "anchored.md",
        textwrap.dedent("""\
            id: anchored-note
            title: Anchored
            type: permanent
            anchors:
              - sec-intro
              - sec-results
        """),
    )

    sync_vault(tmp_path, global_session)

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "anchored-note")
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
        "id: target-ref\ntitle: Target\ntype: permanent",
    )
    _write_md(
        tmp_path / "source.md",
        "id: source-ref\ntitle: Source\ntype: permanent",
        body="See also [[target-ref]] for details.",
    )

    sync_vault(tmp_path, global_session)

    source_note = global_session.scalars(
        select(Note).where(Note.zettel_id == "source-ref")
    ).first()
    target_note = global_session.scalars(
        select(Note).where(Note.zettel_id == "target-ref")
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
            id: target-ref
            title: Target
            type: permanent
            anchors:
              - sec-results
        """),
    )
    _write_md(
        tmp_path / "source.md",
        "id: source-ref\ntitle: Source\ntype: permanent",
        body="See [[target-ref#sec-results]] for details.",
    )

    sync_vault(tmp_path, global_session)

    source_note = global_session.scalars(
        select(Note).where(Note.zettel_id == "source-ref")
    ).first()
    target_note = global_session.scalars(
        select(Note).where(Note.zettel_id == "target-ref")
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
        "id: target-ref\ntitle: Target\ntype: permanent",
    )
    _write_md(
        tmp_path / "source.md",
        "id: source-ref\ntitle: Source\ntype: permanent",
        body="See [[target-ref|the target note]] here.",
    )

    sync_vault(tmp_path, global_session)

    source_note = global_session.scalars(
        select(Note).where(Note.zettel_id == "source-ref")
    ).first()
    target_note = global_session.scalars(
        select(Note).where(Note.zettel_id == "target-ref")
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
        "id: source-ref\ntitle: Source\ntype: permanent",
        body="See [[does-not-exist]] for details.",
    )

    report = sync_vault(tmp_path, global_session)

    assert report.links_created == 0
    assert global_session.scalars(select(Link)).all() == []


def test_sync_idempotent_second_run_no_changes(tmp_path, global_session):
    """Running sync twice does not create duplicate Label or Link rows."""
    _write_md(
        tmp_path / "target.md",
        "id: target-ref\ntitle: Target\ntype: permanent",
    )
    _write_md(
        tmp_path / "source.md",
        "id: source-ref\ntitle: Source\ntype: permanent",
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
        "id: dry-note\ntitle: Dry\ntype: permanent",
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
        "id: target-ref\ntitle: Target\ntype: permanent",
    )
    source_md = _write_md(
        tmp_path / "source.md",
        "id: source-ref\ntitle: Source\ntype: permanent",
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
        "id: proj1-note\ntitle: Proj1 Note\ntype: permanent",
    )
    _write_md(
        proj2 / "note-b.md",
        "id: proj2-note\ntitle: Proj2 Note\ntype: permanent",
    )

    sync_vault(tmp_path, global_session, project_filter="0001AA-proj1")

    assert global_session.scalars(
        select(Note).where(Note.zettel_id == "proj1-note")
    ).first() is not None
    assert global_session.scalars(
        select(Note).where(Note.zettel_id == "proj2-note")
    ).first() is None


def test_sync_path_traversal_in_frontmatter_blocked(tmp_path, global_session):
    """Malicious anchor paths (../../etc/passwd) are rejected — not written to DB."""
    _write_md(
        tmp_path / "malicious.md",
        textwrap.dedent("""\
            id: malicious-note
            title: Evil
            type: permanent
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


def test_sync_creates_citation_rows_from_references_field(tmp_path, global_session):
    """references: list in frontmatter creates Citation rows (bibkeys)."""
    _write_md(
        tmp_path / "cited.md",
        textwrap.dedent("""\
            id: cited-note
            title: Cited
            type: permanent
            references:
              - serway2019
              - griffiths2017
        """),
    )
    sync_vault(tmp_path, global_session)

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "cited-note")
    ).first()
    assert note is not None

    citations = global_session.scalars(
        select(Citation).where(Citation.note_id == note.id)
    ).all()
    keys = {c.citationkey for c in citations}
    assert "serway2019" in keys
    assert "griffiths2017" in keys
