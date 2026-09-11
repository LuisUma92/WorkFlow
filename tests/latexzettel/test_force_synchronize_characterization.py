"""Characterization tests for latexzettel.api.sync.force_synchronize.

These tests pin the CURRENT behaviour of ``force_synchronize`` before a
behaviour-preserving refactor (splitting the C901-21 function into smaller
private helpers). They are written against the unmodified implementation and
must keep passing, unchanged, after the refactor.

Where the current behaviour looks like a bug, it is pinned (not fixed) with a
comment: ``# characterizes current behaviour (possible bug: ...)``.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sqlalchemy import select

from latexzettel.api import sync as sync_mod
from latexzettel.config.settings import NotesPaths
from latexzettel.domain.errors import DocumentsTexNotFound, DomainError
from latexzettel.infra.db import db_session, ensure_tables
from workflow.db.models.notes import Note


def _fetch_note_fields(filename: str) -> dict:
    """Re-fetch a Note by filename in a fresh session.

    `force_synchronize`'s `db_session()` context manager commits + closes on
    exit, which (with SQLAlchemy's default `expire_on_commit=True`) leaves
    any Note instances returned in `ForceSyncResult` detached AND expired —
    accessing their attributes afterwards raises `DetachedInstanceError`.
    This is current behaviour of the module (not something this refactor
    should fix), so tests re-query instead of touching attributes on the
    returned instances directly.
    """
    with db_session() as session:
        note = session.scalars(
            select(Note).where(Note.filename == filename)
        ).first()
        if note is None:
            return {}
        return {
            "filename": note.filename,
            "reference": note.reference,
            "created": note.created,
            "last_edit_date": note.last_edit_date,
            "last_build_date_html": note.last_build_date_html,
            "last_build_date_pdf": note.last_build_date_pdf,
        }


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path) -> NotesPaths:
    """A NotesPaths rooted at a scratch tmp_path, with slipbox pre-created."""
    paths = NotesPaths(root=tmp_path)
    (tmp_path / "notes" / "slipbox").mkdir(parents=True, exist_ok=True)
    return paths


def _write_note(paths: NotesPaths, filename: str, body: str) -> Path:
    p = paths.abs(paths.slipbox_dir / f"{filename}.tex")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _write_documents_tex(paths: NotesPaths, entries: list[tuple[str, str]]) -> Path:
    """entries: list of (reference, filename) -> \\externaldocument[reference-]{filename}"""
    doc_path = paths.abs(paths.documents_tex)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"\\externaldocument[{ref}-]{{{fname}}}" for ref, fname in entries]
    doc_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return doc_path


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


NOTE_BODY_TEMPLATE = (
    "\\label{{{label}}}\n"
    "\\cite{{{citekey}}}\n"
    "\\excref{{{ref}}}\n"
)


# ---------------------------------------------------------------------------
# documents.tex handling
# ---------------------------------------------------------------------------


class TestDocumentsTexHandling:
    def test_missing_documents_tex_created_when_flag_true(self, workspace):
        doc_path = workspace.abs(workspace.documents_tex)
        assert not doc_path.exists()

        result = sync_mod.force_synchronize(
            paths=workspace,
            create_documents_tex_if_missing=True,
        )

        assert doc_path.exists()
        assert doc_path.read_text(encoding="utf-8") == ""
        assert result.tracked_notes == {}
        assert result.added_notes == []
        assert result.updated_notes == []

    def test_missing_documents_tex_raises_when_flag_false(self, workspace):
        doc_path = workspace.abs(workspace.documents_tex)
        assert not doc_path.exists()

        with pytest.raises(DocumentsTexNotFound):
            sync_mod.force_synchronize(
                paths=workspace,
                create_documents_tex_if_missing=False,
            )

    def test_existing_documents_tex_is_not_overwritten(self, workspace):
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        doc_path = _write_documents_tex(workspace, [("RefA", "note-a")])
        original_content = doc_path.read_text(encoding="utf-8")
        _set_mtime(note_a, datetime.now() - timedelta(days=1))

        sync_mod.force_synchronize(paths=workspace)

        assert doc_path.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# DB availability
# ---------------------------------------------------------------------------


class TestDbAvailability:
    def test_raises_domain_error_when_db_unavailable(self, workspace, monkeypatch):
        _write_documents_tex(workspace, [])

        class _UnhealthyHealth:
            ok = False
            error = "boom"

        monkeypatch.setattr(
            sync_mod, "ensure_tables", lambda: _UnhealthyHealth()
        )

        with pytest.raises(DomainError, match="boom"):
            sync_mod.force_synchronize(paths=workspace)


# ---------------------------------------------------------------------------
# Tracked note file existence (create_missing_note_files)
# ---------------------------------------------------------------------------


class TestTrackedNoteFileHandling:
    def test_missing_tracked_note_file_created_when_flag_true(self, workspace):
        _write_documents_tex(workspace, [("RefA", "note-a")])

        result = sync_mod.force_synchronize(
            paths=workspace,
            create_missing_note_files=True,
        )

        note_path = workspace.abs(workspace.slipbox_dir / "note-a.tex")
        assert note_path.exists()
        assert "documentclass" in note_path.read_text(encoding="utf-8")
        assert result.tracked_notes == {"note-a": "RefA"}
        assert len(result.added_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["reference"] == "RefA"

    def test_missing_tracked_note_file_skipped_when_flag_false(self, workspace):
        _write_documents_tex(workspace, [("RefA", "note-a")])

        result = sync_mod.force_synchronize(
            paths=workspace,
            create_missing_note_files=False,
        )

        note_path = workspace.abs(workspace.slipbox_dir / "note-a.tex")
        assert not note_path.exists()
        # tracked_notes still reflects documents.tex parsing...
        assert result.tracked_notes == {"note-a": "RefA"}
        # ...but no DB row was created since the file never existed.
        assert result.added_notes == []
        assert result.updated_notes == []


# ---------------------------------------------------------------------------
# Note row creation / update
# ---------------------------------------------------------------------------


class TestNoteRowSync:
    def test_creates_new_note_row_for_untracked_file(self, workspace):
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        _set_mtime(note_a, datetime(2026, 1, 1, 12, 0, 0))

        result = sync_mod.force_synchronize(paths=workspace)

        assert len(result.added_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["reference"] == "RefA"
        assert fields["created"] == datetime(2026, 1, 1, 12, 0, 0)
        assert fields["last_edit_date"] == datetime(2026, 1, 1, 12, 0, 0)
        assert result.updated_notes == []

    def test_updates_existing_note_row_last_edit_date(self, workspace):
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        old_dt = datetime(2020, 1, 1, 0, 0, 0)
        _set_mtime(note_a, old_dt)
        sync_mod.force_synchronize(paths=workspace)

        new_dt = datetime(2026, 5, 1, 8, 30, 0)
        _set_mtime(note_a, new_dt)
        result = sync_mod.force_synchronize(paths=workspace)

        assert result.added_notes == []
        assert len(result.updated_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["last_edit_date"] == new_dt
        # created is preserved from the first sync, not overwritten.
        assert fields["created"] == old_dt

    def test_reference_change_updates_existing_row(self, workspace):
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        _set_mtime(note_a, datetime(2026, 1, 1))
        sync_mod.force_synchronize(paths=workspace)

        _write_documents_tex(workspace, [("RefA-renamed", "note-a")])
        result = sync_mod.force_synchronize(paths=workspace)

        assert len(result.updated_notes) == 1
        assert _fetch_note_fields("note-a")["reference"] == "RefA-renamed"

    def test_note_reassigned_by_reference_when_filename_changes(self, workspace):
        """
        characterizes current behaviour: if a tracked_notes entry's filename
        doesn't match any Note.filename in DB, but a Note with the same
        `reference` exists, that Note's filename is reassigned (rename flow)
        instead of creating a duplicate Note row.
        """
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        _set_mtime(note_a, datetime(2026, 1, 1))
        sync_mod.force_synchronize(paths=workspace)

        # Rename the physical file and repoint documents.tex to the new
        # filename while keeping the same reference.
        note_b_path = workspace.abs(workspace.slipbox_dir / "note-b.tex")
        note_a.rename(note_b_path)
        _set_mtime(note_b_path, datetime(2026, 2, 1))
        _write_documents_tex(workspace, [("RefA", "note-b")])

        result = sync_mod.force_synchronize(paths=workspace)

        assert result.added_notes == []
        assert len(result.updated_notes) == 1
        fields = _fetch_note_fields("note-b")
        assert fields["reference"] == "RefA"
        assert _fetch_note_fields("note-a") == {}

    def test_note_created_is_set_when_previously_none(self, workspace):
        """
        characterizes current behaviour: an existing Note row with
        created=None gets `created` backfilled from last_edit_date on sync.
        """
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        dt = datetime(2026, 3, 1)
        _set_mtime(note_a, dt)

        # Pre-seed a Note row with created=None to force the backfill branch.
        ensure_tables()
        with db_session() as session:
            session.add(Note(filename="note-a", reference="RefA", created=None))

        result = sync_mod.force_synchronize(paths=workspace)

        assert len(result.updated_notes) == 1
        assert _fetch_note_fields("note-a")["created"] == dt


# ---------------------------------------------------------------------------
# Build dates (html/pdf artifacts)
# ---------------------------------------------------------------------------


class TestBuildDates:
    def test_build_dates_absent_when_artifacts_missing(self, workspace):
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        _set_mtime(note_a, datetime(2026, 1, 1))

        result = sync_mod.force_synchronize(paths=workspace)

        assert len(result.added_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["last_build_date_html"] is None
        assert fields["last_build_date_pdf"] is None

    def test_build_dates_present_when_artifacts_exist(self, workspace):
        """
        characterizes current behaviour: build dates are only stamped for
        the update-existing-row branch (an existing Note found by filename),
        never on first creation of a new Note row in the same pass.
        """
        note_a = _write_note(workspace, "note-a", NOTE_BODY_TEMPLATE.format(
            label="lbl-a", citekey="key-a", ref="note-a"
        ))
        _write_documents_tex(workspace, [("RefA", "note-a")])
        _set_mtime(note_a, datetime(2026, 1, 1))

        html_dir = workspace.abs(workspace.html_dir)
        pdf_dir = workspace.abs(workspace.pdf_dir)
        html_dir.mkdir(parents=True, exist_ok=True)
        pdf_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / "note-a.html"
        pdf_path = pdf_dir / "note-a.pdf"
        html_path.write_text("<html></html>", encoding="utf-8")
        pdf_path.write_bytes(b"%PDF-1.4")
        html_dt = datetime(2026, 1, 2)
        pdf_dt = datetime(2026, 1, 3)
        _set_mtime(html_path, html_dt)
        _set_mtime(pdf_path, pdf_dt)

        # First sync only creates the Note row (added_notes path) — no build
        # dates are stamped yet, per current behaviour.
        first_result = sync_mod.force_synchronize(paths=workspace)
        assert len(first_result.added_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["last_build_date_html"] is None
        assert fields["last_build_date_pdf"] is None

        # Second sync finds the existing row and stamps build dates.
        second_result = sync_mod.force_synchronize(paths=workspace)
        assert len(second_result.updated_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["last_build_date_html"] == html_dt
        assert fields["last_build_date_pdf"] == pdf_dt


# ---------------------------------------------------------------------------
# Labels / citations / links reparse pass
# ---------------------------------------------------------------------------


class TestReparsePass:
    def test_labels_citations_and_links_synced_for_all_db_notes(self, workspace):
        note_a = _write_note(
            workspace,
            "note-a",
            "\\label{lbl-a}\n\\cite{key-a}\n",
        )
        note_b = _write_note(
            workspace,
            "note-b",
            "\\label{lbl-b}\n\\excref[lbl-a]{RefA}\n",
        )
        _write_documents_tex(
            workspace, [("RefA", "note-a"), ("RefB", "note-b")]
        )
        _set_mtime(note_a, datetime(2026, 1, 1))
        _set_mtime(note_b, datetime(2026, 1, 1))

        sync_mod.force_synchronize(paths=workspace)

        with db_session() as session:
            note_a_row = session.scalars(
                select(Note).where(Note.filename == "note-a")
            ).first()
            note_b_row = session.scalars(
                select(Note).where(Note.filename == "note-b")
            ).first()

            assert [lbl.label for lbl in note_a_row.labels] == ["lbl-a"]
            assert [c.citationkey for c in note_a_row.citations] == ["key-a"]

            assert [lbl.label for lbl in note_b_row.labels] == ["lbl-b"]
            assert len(note_b_row.references) == 1
            link = note_b_row.references[0]
            assert link.target.note.reference == "RefA"
            assert link.target.label == "lbl-a"

    def test_note_missing_file_during_reparse_is_skipped(self, workspace):
        """
        characterizes current behaviour: if a Note row exists in DB but its
        backing .tex file has been deleted between the write-pass and the
        reparse-pass, `_update_note_from_file`'s NoteNotFound is swallowed
        and the note is simply skipped (no exception propagates).
        """
        note_a = _write_note(workspace, "note-a", "\\label{lbl-a}\n")
        _write_documents_tex(workspace, [("RefA", "note-a")])
        _set_mtime(note_a, datetime(2026, 1, 1))
        sync_mod.force_synchronize(paths=workspace)

        # Now remove the physical file but keep documents.tex pointing at it
        # with create_missing_note_files=False so no new file gets created,
        # and the tracked-notes loop `continue`s without touching the DB row
        # for this filename either.
        note_a.unlink()

        result = sync_mod.force_synchronize(
            paths=workspace, create_missing_note_files=False
        )

        # No exception raised; row still exists in DB from the prior sync.
        assert result.added_notes == []
        assert result.updated_notes == []


# ---------------------------------------------------------------------------
# timestamp parameter (accepted but unused)
# ---------------------------------------------------------------------------


class TestTimestampParamUnused:
    def test_timestamp_argument_has_no_effect(self, workspace):
        """
        characterizes current behaviour: `timestamp` is accepted for API
        compatibility but never used to set created/last_edit_date — those
        always come from the file mtime, never from the `timestamp` arg.
        """
        note_a = _write_note(workspace, "note-a", "\\label{lbl-a}\n")
        _write_documents_tex(workspace, [("RefA", "note-a")])
        mtime_dt = datetime(2026, 1, 1)
        _set_mtime(note_a, mtime_dt)

        bogus_timestamp = datetime(1999, 1, 1)
        result = sync_mod.force_synchronize(
            paths=workspace, timestamp=bogus_timestamp
        )

        assert len(result.added_notes) == 1
        fields = _fetch_note_fields("note-a")
        assert fields["created"] == mtime_dt
        assert fields["last_edit_date"] == mtime_dt
