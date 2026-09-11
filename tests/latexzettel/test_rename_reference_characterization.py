"""Characterization tests for latexzettel.api.notes.rename_reference.

These tests pin the CURRENT behaviour of ``rename_reference`` byte-for-byte
before a refactor that only extracts helpers (no behaviour change intended).
Do not "fix" surprising behaviour here — pin it and note it as a possible bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workflow.db.models.notes import Label, Link, Note

from latexzettel.api.notes import rename_reference
from latexzettel.config.settings import NotesPaths
from latexzettel.domain.errors import (
    DocumentsTexNotFound,
    NoteNotFound,
    ReferenceAlreadyExists,
)
from latexzettel.infra.db import db_session, ensure_schema_if_needed


def _make_paths(tmp_path: Path) -> NotesPaths:
    paths = NotesPaths(root=tmp_path)
    paths.abs(paths.slipbox_dir).mkdir(parents=True, exist_ok=True)
    return paths


def _write_doc(paths: NotesPaths, content: str) -> Path:
    doc = paths.abs(paths.documents_tex)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(content, encoding="utf-8")
    return doc


def _write_note_file(paths: NotesPaths, filename: str, content: str) -> Path:
    fpath = paths.abs(paths.slipbox_dir) / f"{filename}.tex"
    fpath.write_text(content, encoding="utf-8")
    return fpath


def _create_note(session, *, filename: str, reference: str) -> Note:
    note = Note(filename=filename, reference=reference)
    session.add(note)
    session.flush()
    return note


def test_rename_reference_unknown_old_reference_raises(tmp_path):
    paths = _make_paths(tmp_path)
    _write_doc(paths, "")

    with pytest.raises(NoteNotFound):
        rename_reference(
            old_reference="DoesNotExist",
            new_reference="Whatever",
            paths=paths,
        )


def test_rename_reference_new_reference_collision_raises(tmp_path):
    paths = _make_paths(tmp_path)
    doc_content = (
        "\\externaldocument[OldRef-]{nota_a}\n"
        "\\externaldocument[Taken-]{nota_taken}\n"
    )
    _write_doc(paths, doc_content)

    ensure_schema_if_needed()
    with db_session() as session:
        _create_note(session, filename="nota_a", reference="OldRef")
        _create_note(session, filename="nota_taken", reference="Taken")

    with pytest.raises(ReferenceAlreadyExists):
        rename_reference(
            old_reference="OldRef",
            new_reference="Taken",
            paths=paths,
        )

    # No side effects should have happened: collision is checked before any
    # file mutation.
    assert paths.abs(paths.documents_tex).read_text(encoding="utf-8") == doc_content


@pytest.mark.parametrize(
    "old_reference,new_reference",
    [("", "NewRef"), ("OldRef", ""), ("", "")],
)
def test_rename_reference_empty_args_raise_value_error(tmp_path, old_reference, new_reference):
    paths = _make_paths(tmp_path)
    _write_doc(paths, "")

    with pytest.raises(ValueError):
        rename_reference(
            old_reference=old_reference,
            new_reference=new_reference,
            paths=paths,
        )


def test_rename_reference_documents_tex_missing_raises(tmp_path):
    paths = _make_paths(tmp_path)
    # Deliberately do NOT create notes/documents.tex.

    ensure_schema_if_needed()
    with db_session() as session:
        _create_note(session, filename="nota_a", reference="OldRef")

    with pytest.raises(DocumentsTexNotFound):
        rename_reference(
            old_reference="OldRef",
            new_reference="NewRef",
            paths=paths,
        )


def test_rename_reference_happy_path_rewrites_files_and_db(tmp_path):
    paths = _make_paths(tmp_path)

    doc_content = (
        "\\externaldocument[OldRef-]{nota_a}\n"
        "\\externaldocument[RefB-]{nota_b}\n"
        "\\externaldocument[RefC-]{nota_c}\n"
    )
    _write_doc(paths, doc_content)

    # Note A: the note whose reference is being renamed. Has a label that
    # other notes link back to.
    note_b_content_before = (
        "Ver \\excref{OldRef} y tambien \\exhyperref[sec]{OldRef}.\n"
    )
    note_c_content_before = (
        # Same literal text pattern as note B, but note C is NOT linked to
        # note A's label in the DB. Pins that rewriting is DB-link-driven,
        # not a blind grep-over-all-files rewrite.
        # characterizes current behaviour (possible bug: a note whose text
        # contains a matching \\excref/\\exhyperref pattern but has no
        # corresponding Link row in the DB is silently NOT rewritten, so the
        # rename can leave text referencing a now-nonexistent reference).
        "Ver \\excref{OldRef} tambien.\n"
    )
    note_d_content_before = (
        # "OldRefExtra" is NOT "OldRef" — pins that the backref regex does
        # an exact brace-bounded match, not a substring match, even though
        # note D IS linked to note A's label in the DB.
        "Ver \\excref{OldRefExtra} tambien.\n"
    )
    note_b_path = _write_note_file(paths, "nota_b", note_b_content_before)
    note_c_path = _write_note_file(paths, "nota_c", note_c_content_before)
    note_d_path = _write_note_file(paths, "nota_d", note_d_content_before)
    # note_e is registered in the DB and linked to note A's label but has NO
    # corresponding .tex file on disk — pins the "if not fpath.exists():
    # continue" skip branch.

    ensure_schema_if_needed()
    with db_session() as session:
        note_a = _create_note(session, filename="nota_a", reference="OldRef")
        _create_note(session, filename="nota_b", reference="RefB")
        _create_note(session, filename="nota_c", reference="RefC")
        _create_note(session, filename="nota_d", reference="RefD")
        _create_note(session, filename="nota_e", reference="RefE")

        label = Label(note_id=note_a.id, label="lblA")
        session.add(label)
        session.flush()

        # Link note_b, note_d and note_e back to note_a's label so they are
        # all in the "backref_files" set.
        for fname in ("nota_b", "nota_d", "nota_e"):
            src = session.query(Note).filter(Note.filename == fname).one()
            session.add(Link(source_id=src.id, target_id=label.id))
        session.flush()

    result = rename_reference(
        old_reference="OldRef",
        new_reference="NewRef",
        paths=paths,
    )

    assert result is None

    # documents.tex: only note_a's line is rewritten.
    expected_doc = (
        "\\externaldocument[NewRef-]{nota_a}\n"
        "\\externaldocument[RefB-]{nota_b}\n"
        "\\externaldocument[RefC-]{nota_c}\n"
    )
    assert paths.abs(paths.documents_tex).read_text(encoding="utf-8") == expected_doc

    # note_b: linked backref, exact-match text -> rewritten.
    assert note_b_path.read_text(encoding="utf-8") == (
        "Ver \\excref{NewRef} y tambien \\exhyperref[sec]{NewRef}.\n"
    )

    # note_c: NOT linked in DB -> left byte-identical even though the text
    # pattern matches (see comment above / possible bug).
    assert note_c_path.read_text(encoding="utf-8") == note_c_content_before

    # note_d: linked in DB, but text only has "OldRefExtra" (substring, not
    # exact) -> left byte-identical.
    assert note_d_path.read_text(encoding="utf-8") == note_d_content_before

    # note_e has no file on disk; must not raise.
    assert not (paths.abs(paths.slipbox_dir) / "nota_e.tex").exists()

    # DB: note_a.reference updated.
    with db_session() as session:
        updated = session.query(Note).filter(Note.filename == "nota_a").one()
        assert updated.reference == "NewRef"
        # Collision target from other tests isn't present here; sanity check
        # that no other note's reference was touched.
        untouched = session.query(Note).filter(Note.filename == "nota_b").one()
        assert untouched.reference == "RefB"


def test_rename_reference_update_backrefs_false_skips_backref_rewrite(tmp_path):
    paths = _make_paths(tmp_path)

    doc_content = "\\externaldocument[OldRef-]{nota_a}\n"
    _write_doc(paths, doc_content)

    note_b_content_before = "Ver \\excref{OldRef} tambien.\n"
    note_b_path = _write_note_file(paths, "nota_b", note_b_content_before)

    ensure_schema_if_needed()
    with db_session() as session:
        note_a = _create_note(session, filename="nota_a", reference="OldRef")
        _create_note(session, filename="nota_b", reference="RefB")

        label = Label(note_id=note_a.id, label="lblA")
        session.add(label)
        session.flush()

        note_b = session.query(Note).filter(Note.filename == "nota_b").one()
        session.add(Link(source_id=note_b.id, target_id=label.id))
        session.flush()

    result = rename_reference(
        old_reference="OldRef",
        new_reference="NewRef",
        paths=paths,
        update_backrefs=False,
    )

    assert result is None

    # documents.tex is still rewritten regardless of update_backrefs.
    assert paths.abs(paths.documents_tex).read_text(encoding="utf-8") == (
        "\\externaldocument[NewRef-]{nota_a}\n"
    )

    # Backref file left untouched because update_backrefs=False.
    assert note_b_path.read_text(encoding="utf-8") == note_b_content_before

    # DB reference is still updated.
    with db_session() as session:
        updated = session.query(Note).filter(Note.filename == "nota_a").one()
        assert updated.reference == "NewRef"
