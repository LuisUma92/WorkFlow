# tests/latexzettel/test_render_characterization.py
"""
Characterization tests for ``latexzettel.api.render`` (``render_note`` and
``render_updates``), written BEFORE refactoring those functions to reduce
flake8 C901 complexity.

Important finding (pinned, not fixed — see individual tests marked
"characterizes current behaviour"):

``db_session()`` (``latexzettel.infra.db.db_session``) commits and then
closes its ``Session`` on ``__exit__``. SQLAlchemy's default
``expire_on_commit=True`` means every attribute of any ORM instance fetched
inside a ``with db_session() as session:`` block is expired at commit time;
once the session is subsequently closed, that instance is detached and any
attribute access (not just relationship access) raises
``sqlalchemy.orm.exc.DetachedInstanceError``.

Both ``render_note`` and ``render_updates`` fetch ``Note`` rows this way and
then access attributes *outside* the ``with`` block that fetched them. In
practice this means most of the "success" logic in both functions
(building the referenced-by section, invoking the renderer, updating build
timestamps, the timestamp-based re-render extension in ``render_updates``)
is unreachable today for any note that actually exists in the DB. We pin
this rather than silently "fixing" it during a behaviour-preserving
refactor.

To still characterize the *reachable* pure logic, the private helper
functions (``_build_referenced_by_section``, ``_inject_external_documents_for_html``,
``_prepare_document_for_render``, ``_load_note_tex``) are tested directly,
and ``render_updates``'s orchestration logic (steps 3-5) is characterized by
stubbing ``render_note`` and ``synchronize`` and using plain (non-ORM)
note-like objects, which sidesteps the detached-session bug entirely for
that part of the test matrix.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm.exc import DetachedInstanceError

from workflow.db.models.notes import Note

from latexzettel.api import render as render_mod
from latexzettel.api.render import (
    RenderResult,
    RenderUpdatesResult,
    _build_referenced_by_section,
    _inject_external_documents_for_html,
    _load_note_tex,
    _prepare_document_for_render,
    biber,
    render_note,
    render_updates,
)
from latexzettel.api.sync import SyncResult
from latexzettel.config.settings import RenderSettings, build_settings
from latexzettel.domain.errors import DomainError, NoteNotFound
from latexzettel.domain.types import RenderFormat
from latexzettel.infra import processes
from latexzettel.infra.db import db_session, ensure_tables


class Obj:
    """Plain attribute bag with identity-based hash/eq (unlike SimpleNamespace,
    which defines ``__eq__`` and is therefore unhashable). Used to stand in for
    ORM objects (Note/Label/Link) in tests that must sidestep the detached-session
    bug described above by never touching a real DB-backed instance."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# =============================================================================
# Fixtures / helpers
# =============================================================================


@pytest.fixture
def settings(tmp_path):
    return build_settings(root=tmp_path)


def write_note_tex(paths, filename: str, body: str = "Cuerpo\n") -> None:
    path = paths.abs(paths.slipbox_dir / f"{filename}.tex")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\\documentclass{../template/texnote}\n"
        "\\subimport{../template}{preamble.tex}\n"
        "\\begin{document}\n"
        f"{body}"
        "\\end{document}\n",
        encoding="utf-8",
    )


def add_db_note(**kwargs) -> None:
    ensure_tables()
    with db_session() as session:
        session.add(Note(**kwargs))


class RecordingRenderer:
    def __init__(self, returncode: int = 0, stdout: bytes = b"out", stderr: bytes = b"err"):
        self.calls: list[dict] = []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, *, command, options, input_tex, cwd, check):
        self.calls.append(
            {
                "command": command,
                "options": list(options),
                "input_tex": input_tex,
                "cwd": cwd,
                "check": check,
            }
        )
        return processes.ProcessResult(
            args=[command, *options],
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


class RecordingBiber:
    def __init__(self, returncode: int = 0):
        self.calls: list[dict] = []
        self.returncode = returncode

    def __call__(self, filename, *, folder, check=False):
        self.calls.append({"filename": filename, "folder": folder, "check": check})
        return processes.ProcessResult(
            args=["biber", filename], returncode=self.returncode, stdout=b"", stderr=b""
        )


@pytest.fixture
def fake_renderer(monkeypatch):
    fake = RecordingRenderer()
    monkeypatch.setattr(processes, "run_latex_renderer", fake)
    return fake


@pytest.fixture
def fake_biber_process(monkeypatch):
    fake = RecordingBiber()
    monkeypatch.setattr(processes, "run_biber", fake)
    return fake


@pytest.fixture
def fake_render_note(monkeypatch):
    """Stub ``render_mod.render_note`` used internally by ``render_updates``."""
    calls: list[dict] = []
    outcomes: dict[str, bool] = {}

    def _fake(*, filename, format, run_biber, settings, paths, timestamp, check):
        calls.append(
            {
                "filename": filename,
                "format": format,
                "run_biber": run_biber,
                "timestamp": timestamp,
                "check": check,
            }
        )
        ok = outcomes.get(filename, True)
        return RenderResult(
            filename=filename,
            format=format,
            ok=ok,
            returncode=0 if ok else 1,
            stdout=b"",
            stderr=b"",
        )

    monkeypatch.setattr(render_mod, "render_note", _fake)
    return SimpleNamespace(calls=calls, outcomes=outcomes)


# =============================================================================
# biber() — thin wrapper
# =============================================================================


def test_biber_delegates_to_processes_run_biber(fake_biber_process, tmp_path):
    result = biber(filename="n1", folder=tmp_path, check=True)

    assert fake_biber_process.calls == [{"filename": "n1", "folder": tmp_path, "check": True}]
    assert result.args == ["biber", "n1"]
    assert result.ok is True


# =============================================================================
# Pure helpers used by render_note
# =============================================================================


class TestBuildReferencedBySection:
    def test_empty_set_returns_empty_string(self):
        assert _build_referenced_by_section(set()) == ""

    def test_single_ref(self):
        result = _build_referenced_by_section({"NoteB"})
        assert result == (
            "\\section*{Referenced In}\n\\begin{itemize}\n"
            "\\item \\excref{NoteB}\\end{itemize}"
        )

    def test_multiple_refs_all_present(self):
        result = _build_referenced_by_section({"A", "B"})
        assert "\\item \\excref{A}" in result
        assert "\\item \\excref{B}" in result
        assert result.startswith("\\section*{Referenced In}\n\\begin{itemize}\n")
        assert result.endswith("\\end{itemize}")


class TestInjectExternalDocumentsForHtml:
    def test_no_references_returns_empty(self):
        assert _inject_external_documents_for_html(set()) == ""

    def test_reference_without_html_build_date_is_skipped(self):
        ref = Obj(last_build_date_html=None, reference="R", filename="f")
        assert _inject_external_documents_for_html({ref}) == ""

    def test_reference_with_html_build_date_is_included(self):
        ref = Obj(
            last_build_date_html=datetime(2026, 1, 1), reference="R", filename="f"
        )
        assert _inject_external_documents_for_html({ref}) == "\\externaldocument[R-]{f}\n"

    def test_reference_missing_attribute_treated_as_none(self):
        # getattr(..., None) fallback: a bare object() has no last_build_date_html.
        assert _inject_external_documents_for_html({object()}) == ""


class TestPrepareDocumentForRender:
    RAW_TEX = (
        "\\documentclass{../template/texnote}\n"
        "\\subimport{../template}{preamble.tex}\n"
        "\\begin{document}\nHola\n\\end{document}\nTRAILING_GARBAGE"
    )

    def test_pdf_trims_after_end_document_and_reappends_it(self):
        doc = _prepare_document_for_render(
            raw_tex=self.RAW_TEX,
            format=RenderFormat.PDF,
            referenced_by_section="",
            external_documents="",
        )
        assert doc == (
            "\\documentclass{../template/texnote}\n"
            "\\subimport{../template}{preamble.tex}\n"
            "\\begin{document}\nHola\n\\end{document}"
        )
        assert "TRAILING_GARBAGE" not in doc

    def test_pdf_inserts_referenced_by_section_before_end_document(self):
        doc = _prepare_document_for_render(
            raw_tex=self.RAW_TEX,
            format=RenderFormat.PDF,
            referenced_by_section="\\section*{Referenced In}",
            external_documents="",
        )
        assert doc == (
            "\\documentclass{../template/texnote}\n"
            "\\subimport{../template}{preamble.tex}\n"
            "\\begin{document}\nHola\n\\section*{Referenced In}\\end{document}"
        )

    def test_html_replaces_preamble_and_injects_external_documents(self):
        doc = _prepare_document_for_render(
            raw_tex=self.RAW_TEX,
            format=RenderFormat.HTML,
            referenced_by_section="",
            external_documents="\\externaldocument[R-]{f}\n",
        )
        # characterizes current behaviour (possible bug: external_documents is
        # injected TWICE for HTML — once after \subimport{...}{preamble.tex}
        # (which is also rewritten to preamble_html.tex) and again after
        # \documentclass{../template/texnote}, duplicating the
        # \externaldocument line).
        assert doc == (
            "\\documentclass{../template/texnote}\n\\externaldocument[R-]{f}\n\n"
            "\\subimport{../template}{preamble_html.tex}\n\\externaldocument[R-]{f}\n\n"
            "\\begin{document}\nHola\n\\end{document}"
        )
        assert doc.count("\\externaldocument[R-]{f}") == 2


class TestLoadNoteTex:
    def test_returns_content_when_file_exists(self, settings):
        write_note_tex(settings.paths, "n1", body="Cuerpo especial\n")
        content = _load_note_tex(settings.paths, "n1")
        assert "Cuerpo especial" in content

    def test_raises_note_not_found_when_file_missing(self, settings):
        with pytest.raises(NoteNotFound, match="No existe el archivo de la nota"):
            _load_note_tex(settings.paths, "ghost")


# =============================================================================
# render_note() — reachable branches
# =============================================================================


class TestRenderNoteReachableBranches:
    def test_db_unavailable_raises_domain_error(self, settings, monkeypatch):
        monkeypatch.setattr(
            render_mod,
            "ensure_tables",
            lambda: SimpleNamespace(ok=False, initialized=False, error="boom"),
        )
        with pytest.raises(DomainError, match="DB no disponible: boom"):
            render_note(filename="missing", settings=settings.render, paths=settings.paths)

    def test_note_not_found_raises(self, settings):
        with pytest.raises(NoteNotFound, match="filename='ghost'"):
            render_note(filename="ghost", settings=settings.render, paths=settings.paths)

    def test_uses_now_for_timestamp_when_not_given(self, settings, monkeypatch):
        calls = []

        def fake_now():
            calls.append(1)
            return datetime(2030, 1, 1)

        monkeypatch.setattr(render_mod, "now", fake_now)

        with pytest.raises(NoteNotFound):
            render_note(filename="ghost", settings=settings.render, paths=settings.paths)

        assert calls == [1]

    def test_unsupported_format_raises_value_error(self, settings):
        add_db_note(filename="n1", reference="N1")
        custom_settings = RenderSettings(
            default_format="pdf",
            supported_formats=("pdf",),
            renderers={},
        )
        with pytest.raises(ValueError, match="Formato no soportado"):
            render_note(
                filename="n1",
                format=RenderFormat.PDF,
                settings=custom_settings,
                paths=settings.paths,
            )

    def test_missing_tex_file_raises_note_not_found(self, settings):
        add_db_note(filename="n1", reference="N1")
        with pytest.raises(NoteNotFound, match="No existe el archivo de la nota"):
            render_note(filename="n1", settings=settings.render, paths=settings.paths)

    def test_render_biber_false_hits_detached_instance_bug(self, settings, fake_renderer):
        # characterizes current behaviour (possible bug: db_session() commits
        # and closes its Session before render_note reads note.labels /
        # note.references; accessing those attributes on the now-detached
        # Note raises DetachedInstanceError, so the renderer is never
        # actually invoked for any note that exists in the DB).
        add_db_note(filename="n1", reference="N1")
        write_note_tex(settings.paths, "n1")

        with pytest.raises(DetachedInstanceError):
            render_note(filename="n1", settings=settings.render, paths=settings.paths)

        assert fake_renderer.calls == []

    def test_render_biber_true_hits_detached_instance_bug_before_biber_runs(
        self, settings, fake_renderer, fake_biber_process
    ):
        # characterizes current behaviour (possible bug: the DetachedInstanceError
        # above is raised from the *first* recursive render_note(run_biber=False)
        # call, so biber() is never actually invoked despite run_biber=True).
        add_db_note(filename="n1", reference="N1")
        write_note_tex(settings.paths, "n1")

        with pytest.raises(DetachedInstanceError):
            render_note(
                filename="n1", run_biber=True, settings=settings.render, paths=settings.paths
            )

        assert fake_renderer.calls == []
        assert fake_biber_process.calls == []


# =============================================================================
# render_updates() — reachable / stubbed orchestration
# =============================================================================


class TestRenderUpdatesOrchestration:
    def test_db_unavailable_raises_domain_error(self, settings, monkeypatch):
        monkeypatch.setattr(
            render_mod,
            "ensure_tables",
            lambda: SimpleNamespace(ok=False, initialized=False, error="boom"),
        )
        with pytest.raises(DomainError, match="DB no disponible: boom"):
            render_updates(settings=settings.render, paths=settings.paths)

    def test_renders_updated_notes_with_their_own_run_biber_flag(
        self, settings, fake_render_note, monkeypatch
    ):
        note_a = Obj(filename="a")
        note_b = Obj(filename="b")
        sync_res = SyncResult(
            updated_notes=[note_a, note_b],
            new_or_modified_links=[],
            run_biber={note_a: True, note_b: False},
        )
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)
        ts = datetime(2026, 1, 1, 12, 0, 0)

        result = render_updates(
            format=RenderFormat.PDF,
            settings=settings.render,
            paths=settings.paths,
            timestamp=ts,
        )

        assert result == RenderUpdatesResult(
            rendered=["a", "b"], rerendered_targets=[], rerendered_sources=[]
        )
        assert fake_render_note.calls == [
            {
                "filename": "a",
                "format": RenderFormat.PDF,
                "run_biber": True,
                "timestamp": ts,
                "check": False,
            },
            {
                "filename": "b",
                "format": RenderFormat.PDF,
                "run_biber": False,
                "timestamp": ts,
                "check": False,
            },
        ]

    def test_missing_run_biber_entry_defaults_to_false(
        self, settings, fake_render_note, monkeypatch
    ):
        note_a = Obj(filename="a")
        sync_res = SyncResult(updated_notes=[note_a], new_or_modified_links=[], run_biber={})
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)

        render_updates(settings=settings.render, paths=settings.paths)

        assert fake_render_note.calls[0]["run_biber"] is False

    def test_render_failure_excluded_from_rendered_list(
        self, settings, fake_render_note, monkeypatch
    ):
        note_a = Obj(filename="a")
        fake_render_note.outcomes["a"] = False
        sync_res = SyncResult(updated_notes=[note_a], new_or_modified_links=[], run_biber={})
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)

        result = render_updates(settings=settings.render, paths=settings.paths)

        assert result.rendered == []

    def test_rerenders_targets_and_sources_once_each_and_excludes_failures(
        self, settings, fake_render_note, monkeypatch
    ):
        note_src = Obj(filename="src")
        note_tgt_ok = Obj(filename="tgt-ok")
        note_tgt_fail = Obj(filename="tgt-fail")
        label_ok = Obj(note=note_tgt_ok)
        label_fail = Obj(note=note_tgt_fail)

        link1 = Obj(source=note_src, target=label_ok)
        link1_dup = Obj(source=note_src, target=label_ok)  # dedup expected
        link2 = Obj(source=note_src, target=label_fail)

        fake_render_note.outcomes["tgt-fail"] = False

        sync_res = SyncResult(
            updated_notes=[], new_or_modified_links=[link1, link1_dup, link2], run_biber={}
        )
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)

        result = render_updates(settings=settings.render, paths=settings.paths)

        assert result.rendered == []
        assert result.rerendered_targets == ["tgt-ok"]
        assert result.rerendered_sources == ["src"]
        # Every re-render call uses run_biber=False regardless of the sync run_biber dict.
        assert all(call["run_biber"] is False for call in fake_render_note.calls)

    def test_threads_html_format_through_render_note_calls(
        self, settings, fake_render_note, monkeypatch
    ):
        note_a = Obj(filename="a")
        sync_res = SyncResult(updated_notes=[note_a], new_or_modified_links=[], run_biber={})
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)

        render_updates(format=RenderFormat.HTML, settings=settings.render, paths=settings.paths)

        assert fake_render_note.calls[0]["format"] == RenderFormat.HTML

    def test_uses_now_for_timestamp_when_not_given(
        self, settings, fake_render_note, monkeypatch
    ):
        fixed_now = datetime(2030, 5, 5, 5, 5, 5)
        monkeypatch.setattr(render_mod, "now", lambda: fixed_now)
        note_a = Obj(filename="a")
        sync_res = SyncResult(updated_notes=[note_a], new_or_modified_links=[], run_biber={})
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)

        render_updates(settings=settings.render, paths=settings.paths)

        assert fake_render_note.calls[0]["timestamp"] == fixed_now

    def test_timestamp_extension_branch_hits_detached_instance_bug(self, settings, monkeypatch):
        # characterizes current behaviour (possible bug: `all_notes` is fetched
        # inside its own `with db_session():` block; outside that block,
        # `note.last_build_date_pdf` / `note.last_edit_date` are accessed to
        # decide whether the note needs a render "by timestamp". This raises
        # DetachedInstanceError for any real Note row in the DB. Note also
        # that `note in updated` can never skip a real note fetched by this
        # query, because synchronize()'s `updated_notes` come from a
        # *different*, already-closed session — the Note instances are never
        # identity-equal even when they represent the same underlying row.)
        add_db_note(filename="n1", reference="N1")
        sync_res = SyncResult(updated_notes=[], new_or_modified_links=[], run_biber={})
        monkeypatch.setattr(render_mod, "synchronize", lambda *, paths: sync_res)

        with pytest.raises(DetachedInstanceError):
            render_updates(settings=settings.render, paths=settings.paths)
