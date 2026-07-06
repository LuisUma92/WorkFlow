"""Tests for workflow.notes.sync.sync_note_files — Pass-1 equivalent for an explicit
file list (Wave 0 D1, tasks/plans/2026-07-05-wave0-harvest-loop-plan.md Phase 1).

sync_note_files() is the entry point `lectures split --sync` uses to index freshly
split notes without re-scanning the whole vault. It shares Pass 2-5
(_run_write_passes) with sync_vault() but NEVER runs the orphan-drop pass — a
partial file list must never delete rows for notes outside that list.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import Concept, Content, DisciplineArea, MainTopic, Topic
from workflow.db.models.notes import Label, Link, Note, NoteConcept, NoteEdge
from workflow.notes.sync import SyncReport, sync_note_files, sync_vault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    content = f"---\n{frontmatter.strip()}\n---\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


def _enable_fk(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def engine():
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.project  # noqa: F401
    import workflow.db.models.notes  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401

    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def seeded_concept(session):
    """Seed one resolvable Concept ('known-concept') for the strict/lenient tests."""
    da = DisciplineArea(code="SC0001", name="Science", discipline_num=1, topic_num=1, area_initials="SC")
    session.add(da)
    session.flush()
    mt = MainTopic(code="SC0001", name="Physics", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    tp = Topic(discipline_area_id=da.id, name="Mechanics", serial_number=1)
    session.add(tp)
    session.flush()
    ct = Content(topic_id=tp.id, name="Classical Mechanics")
    session.add(ct)
    session.flush()
    c = Concept(code="known-concept", label="Known", content_id=ct.id, domain="Información")
    session.add(c)
    session.commit()
    return c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sync_note_files_creates_note_and_edge_rows(tmp_path, session):
    """Two explicit files (one derived_from the other) get Note + NoteEdge rows."""
    target = _write_md(
        tmp_path / "target.md",
        "id: target-note\ntitle: Target\ntype: permanent",
    )
    source = _write_md(
        tmp_path / "source.md",
        textwrap.dedent("""\
            id: source-note
            title: Source
            type: permanent
            relations:
              derived_from:
                - id: target-note
                  type: continuation
        """),
    )

    report = sync_note_files([target, source], session)
    session.commit()

    assert isinstance(report, SyncReport)
    assert report.notes_scanned == 2

    source_note = session.scalars(select(Note).where(Note.zettel_id == "source-note")).first()
    target_note = session.scalars(select(Note).where(Note.zettel_id == "target-note")).first()
    assert source_note is not None
    assert target_note is not None

    edges = session.scalars(
        select(NoteEdge).where(NoteEdge.source_id == source_note.id)
    ).all()
    assert len(edges) == 1
    assert edges[0].target_id == target_note.id


def test_sync_note_files_matches_sync_vault_output(tmp_path, session):
    """sync_note_files on the whole set == sync_vault on the same directory."""
    _write_md(tmp_path / "a.md", "id: a\ntitle: A\ntype: permanent")
    _write_md(
        tmp_path / "b.md",
        "id: b\ntitle: B\ntype: permanent",
        body="See [[a]].",
    )
    paths = [tmp_path / "a.md", tmp_path / "b.md"]

    report = sync_note_files(paths, session)
    session.commit()

    assert report.notes_scanned == 2
    assert report.links_created == 1
    note_a = session.scalars(select(Note).where(Note.zettel_id == "a")).first()
    note_b = session.scalars(select(Note).where(Note.zettel_id == "b")).first()
    assert note_a is not None and note_b is not None

    label = session.scalars(
        select(Label).where(Label.note_id == note_a.id, Label.label == "__note__")
    ).first()
    link = session.scalars(
        select(Link).where(Link.source_id == note_b.id, Link.target_id == label.id)
    ).first()
    assert link is not None


def test_sync_note_files_idempotent(tmp_path, session):
    """Calling sync_note_files twice on the same paths keeps row counts stable."""
    target = _write_md(tmp_path / "t2.md", "id: t2\ntitle: T\ntype: permanent")
    source = _write_md(
        tmp_path / "s2.md",
        textwrap.dedent("""\
            id: s2
            title: S
            type: permanent
            concepts:
              - known-concept
            relations:
              derived_from:
                - id: t2
                  type: continuation
        """),
        body="See [[t2]].",
    )

    sync_note_files([target, source], session)
    session.commit()
    labels_1 = session.query(Label).count()
    links_1 = session.query(Link).count()
    edges_1 = session.query(NoteEdge).count()

    sync_note_files([target, source], session)
    session.commit()
    labels_2 = session.query(Label).count()
    links_2 = session.query(Link).count()
    edges_2 = session.query(NoteEdge).count()

    assert labels_1 == labels_2
    assert links_1 == links_2
    assert edges_1 == edges_2


def test_sync_note_files_idempotent_concept_links(tmp_path, session, seeded_concept):
    """NoteConcept row count is stable across repeated sync_note_files calls."""
    note_path = _write_md(
        tmp_path / "c1.md",
        textwrap.dedent("""\
            id: c1
            title: C1
            type: permanent
            concepts:
              - known-concept
        """),
    )

    sync_note_files([note_path], session)
    session.commit()
    count_1 = session.query(NoteConcept).count()

    sync_note_files([note_path], session)
    session.commit()
    count_2 = session.query(NoteConcept).count()

    assert count_1 == count_2 == 1


def test_sync_note_files_unknown_concept_reports_issue_no_row(tmp_path, session):
    """Unknown concept slug → issue reported, no NoteConcept row, no exception."""
    note_path = _write_md(
        tmp_path / "unknown.md",
        textwrap.dedent("""\
            id: unknown-note
            title: Unknown
            type: permanent
            concepts:
              - nonexistent-code
        """),
    )

    report = sync_note_files([note_path], session)
    session.commit()

    rows = session.scalars(select(NoteConcept)).all()
    assert rows == []
    assert len(report.concept_issues) == 1
    assert report.concept_issues[0]["severity"] == "warning"
    assert "nonexistent-code" in report.concept_issues[0]["message"]


def test_sync_note_files_does_not_drop_links_outside_scope(tmp_path, session):
    """Regression guard: syncing a subset must not orphan-drop links for notes
    outside the given `paths`, even though `sync_vault` created them earlier."""
    dir_a = tmp_path / "vault"
    dir_a.mkdir()
    _write_md(dir_a / "target.md", "id: target-b\ntitle: B\ntype: permanent")
    source = _write_md(
        dir_a / "source.md",
        "id: source-a\ntitle: A\ntype: permanent",
        body="See [[target-b]].",
    )

    # Full directory sync first — creates the Link row.
    sync_vault(dir_a, session)
    session.commit()
    assert session.scalars(select(Link)).all() != []

    # Now re-sync only `source` via the explicit file-list entry point.
    report = sync_note_files([source], session)
    session.commit()

    assert report.orphans_dropped == 0
    # The Link created by the earlier full sync must still be present.
    assert session.scalars(select(Link)).all() != []
    # And the `target` note (not in this call's paths) must still exist.
    assert session.scalars(
        select(Note).where(Note.zettel_id == "target-b")
    ).first() is not None
