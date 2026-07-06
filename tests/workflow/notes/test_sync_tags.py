"""Wave 0 gap fix — sync_vault materializes Tag/NoteTag rows from frontmatter tags:.

Gap: workflow notes sync had zero tag ingestion (grep-confirmed). Frontmatter
`tags: [a, b]` (simple kebab strings, per vault exemplar format) must be
get-or-created as Tag rows and linked via NoteTag, with REPLACE semantics per
note (frontmatter is truth) — mirrors the additive pattern of
_sync_note_concepts but adds stale-removal since tags are fully reconcilable
(no external taxonomy dependency the way concepts have).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from sqlalchemy import select

from workflow.db.models.notes import Note, NoteTag, Tag
from workflow.notes.sync import SyncReport, sync_vault


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    content = f"---\n{frontmatter.strip()}\n---\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


def _tag_names_for(session, note_id: int) -> set[str]:
    rows = session.scalars(
        select(Tag.name)
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .where(NoteTag.note_id == note_id)
    ).all()
    return set(rows)


def test_sync_creates_tag_and_note_tag_rows(tmp_path, global_session):
    _write_md(
        tmp_path / "tagged.md",
        textwrap.dedent("""\
            id: tagged-note
            title: Tagged
            type: permanent
            tags:
              - physics
              - mechanics
        """),
    )

    report = sync_vault(tmp_path, global_session)
    global_session.commit()

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "tagged-note")
    ).first()
    assert note is not None

    names = _tag_names_for(global_session, note.id)
    assert names == {"physics", "mechanics"}
    assert report.tags_created == 2
    assert report.tag_links_created == 2


def test_sync_tag_reused_across_notes_not_recreated(tmp_path, global_session):
    _write_md(
        tmp_path / "a.md",
        "id: tag-a\ntitle: A\ntype: permanent\ntags:\n  - shared\n",
    )
    _write_md(
        tmp_path / "b.md",
        "id: tag-b\ntitle: B\ntype: permanent\ntags:\n  - shared\n",
    )

    report = sync_vault(tmp_path, global_session)
    global_session.commit()

    tags = global_session.scalars(select(Tag).where(Tag.name == "shared")).all()
    assert len(tags) == 1
    assert report.tags_created == 1
    assert report.tag_links_created == 2


def test_sync_idempotent_double_run(tmp_path, global_session):
    _write_md(
        tmp_path / "idem.md",
        "id: tag-idem\ntitle: Idem\ntype: permanent\ntags:\n  - stable\n",
    )

    sync_vault(tmp_path, global_session)
    global_session.commit()
    first_tag_count = global_session.query(Tag).count()
    first_link_count = global_session.query(NoteTag).count()

    report2 = sync_vault(tmp_path, global_session)
    global_session.commit()

    assert global_session.query(Tag).count() == first_tag_count
    assert global_session.query(NoteTag).count() == first_link_count
    assert report2.tags_created == 0
    assert report2.tag_links_created == 0


def test_sync_replace_semantics_removes_stale_tag_on_resync(tmp_path, global_session):
    path = _write_md(
        tmp_path / "shift.md",
        "id: tag-shift\ntitle: Shift\ntype: permanent\ntags:\n  - old-tag\n  - keep-tag\n",
    )

    sync_vault(tmp_path, global_session)
    global_session.commit()

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "tag-shift")
    ).first()
    assert _tag_names_for(global_session, note.id) == {"old-tag", "keep-tag"}

    # Re-write frontmatter: drop old-tag, add new-tag, keep keep-tag
    _write_md(
        path,
        "id: tag-shift\ntitle: Shift\ntype: permanent\ntags:\n  - keep-tag\n  - new-tag\n",
    )

    sync_vault(tmp_path, global_session)
    global_session.commit()

    assert _tag_names_for(global_session, note.id) == {"keep-tag", "new-tag"}
    # Tag row for old-tag still exists globally (not deleted), just unlinked
    old_tag = global_session.scalars(select(Tag).where(Tag.name == "old-tag")).first()
    assert old_tag is not None
    links = global_session.scalars(
        select(NoteTag).where(NoteTag.note_id == note.id, NoteTag.tag_id == old_tag.id)
    ).all()
    assert links == []


def test_sync_empty_tags_list_clears_all_links(tmp_path, global_session):
    path = _write_md(
        tmp_path / "clear.md",
        "id: tag-clear\ntitle: Clear\ntype: permanent\ntags:\n  - one\n  - two\n",
    )
    sync_vault(tmp_path, global_session)
    global_session.commit()

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "tag-clear")
    ).first()
    assert _tag_names_for(global_session, note.id) == {"one", "two"}

    _write_md(path, "id: tag-clear\ntitle: Clear\ntype: permanent\ntags: []\n")
    sync_vault(tmp_path, global_session)
    global_session.commit()

    assert _tag_names_for(global_session, note.id) == set()


def test_sync_malformed_tags_non_list_warns_and_skips(tmp_path, global_session):
    _write_md(
        tmp_path / "malformed.md",
        "id: tag-malformed\ntitle: Malformed\ntype: permanent\ntags: not-a-list\n",
    )

    report = sync_vault(tmp_path, global_session)
    global_session.commit()

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "tag-malformed")
    ).first()
    assert _tag_names_for(global_session, note.id) == set()
    assert report.tags_created == 0
    assert report.tag_links_created == 0
    assert any(
        issue["severity"] == "warning" and "tag-malformed" in issue["message"]
        for issue in report.tag_issues
    )


def test_sync_malformed_tag_entry_skipped_valid_ones_kept(tmp_path, global_session):
    _write_md(
        tmp_path / "mixed.md",
        textwrap.dedent("""\
            id: tag-mixed
            title: Mixed
            type: permanent
            tags:
              - good-tag
              - 42
        """),
    )

    report = sync_vault(tmp_path, global_session)
    global_session.commit()

    note = global_session.scalars(
        select(Note).where(Note.zettel_id == "tag-mixed")
    ).first()
    assert _tag_names_for(global_session, note.id) == {"good-tag"}
    assert any(issue["severity"] == "warning" for issue in report.tag_issues)


def test_sync_report_has_tag_fields_default_zero(tmp_path, global_session):
    report = sync_vault(tmp_path, global_session)
    assert isinstance(report, SyncReport)
    assert report.tags_created == 0
    assert report.tag_links_created == 0
    assert report.tag_issues == []
