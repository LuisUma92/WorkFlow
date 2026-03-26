"""Tests for workflow.lecture.linker — Phase 5b (TDD RED → GREEN)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from workflow.db.base import LocalBase
from workflow.db.models.notes import Citation, Label, Link, Note
from workflow.lecture.linker import ExtractedReference, LinkResult, extract_references, link_lecture_files


# ── ExtractedReference shape ────────────────────────────────────────────────


def test_extracted_reference_is_frozen() -> None:
    """ExtractedReference is a frozen dataclass."""
    ref = ExtractedReference(ref_type="cite", key="k", source_file="f.tex", line_number=1)
    with pytest.raises((AttributeError, TypeError)):
        ref.key = "other"  # type: ignore[misc]


# ── extract_references ──────────────────────────────────────────────────────


class TestExtractReferences:
    def test_extract_cite(self) -> None:
        text = r"See \cite{serway2019} for details."
        refs = extract_references(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "cite"
        assert refs[0].key == "serway2019"

    def test_extract_multiple_cites_in_one_command(self) -> None:
        text = r"\cite{book1,book2,book3}"
        refs = extract_references(text)
        cites = [r for r in refs if r.ref_type == "cite"]
        assert len(cites) == 3
        assert {r.key for r in cites} == {"book1", "book2", "book3"}

    def test_extract_label(self) -> None:
        text = r"\label{eq:gauss}"
        refs = extract_references(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "label"
        assert refs[0].key == "eq:gauss"

    def test_extract_ref(self) -> None:
        text = r"See equation \ref{eq:gauss}"
        refs = extract_references(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "ref"
        assert refs[0].key == "eq:gauss"

    def test_extract_eqref(self) -> None:
        text = r"From \eqref{eq:maxwell}"
        refs = extract_references(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "ref"
        assert refs[0].key == "eq:maxwell"

    def test_extract_input(self) -> None:
        text = r"\input{chapters/intro}"
        refs = extract_references(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "input"
        assert refs[0].key == "chapters/intro"

    def test_extract_mixed(self) -> None:
        text = r"\label{sec:intro} As shown in \ref{eq:gauss} and \cite{serway}"
        refs = extract_references(text)
        assert len(refs) == 3
        types = {r.ref_type for r in refs}
        assert types == {"label", "ref", "cite"}

    def test_no_references(self) -> None:
        refs = extract_references("Just plain text, no LaTeX refs.")
        assert refs == []

    def test_line_numbers(self) -> None:
        text = "line 1\n\\cite{ref1}\nline 3\n\\ref{label1}"
        refs = extract_references(text)
        cite_ref = next(r for r in refs if r.ref_type == "cite")
        ref_ref = next(r for r in refs if r.ref_type == "ref")
        assert cite_ref.line_number == 2
        assert ref_ref.line_number == 4

    def test_source_file_stored(self) -> None:
        text = r"\cite{key1}"
        refs = extract_references(text, source_file="chapter01.tex")
        assert refs[0].source_file == "chapter01.tex"

    def test_source_file_default_empty(self) -> None:
        text = r"\cite{key1}"
        refs = extract_references(text)
        assert refs[0].source_file == ""

    def test_cite_keys_stripped_of_whitespace(self) -> None:
        text = r"\cite{book1, book2}"
        refs = extract_references(text)
        keys = {r.key for r in refs}
        assert "book1" in keys
        assert "book2" in keys

    def test_multiple_separate_cites(self) -> None:
        text = r"\cite{a} and \cite{b}"
        refs = extract_references(text)
        cites = [r for r in refs if r.ref_type == "cite"]
        assert len(cites) == 2

    def test_empty_string(self) -> None:
        refs = extract_references("")
        assert refs == []

    def test_commented_line_ignored(self) -> None:
        """References after a % comment char on same line are not extracted."""
        text = "% \\cite{ignored}\n\\cite{real}"
        refs = extract_references(text)
        keys = [r.key for r in refs if r.ref_type == "cite"]
        assert "real" in keys
        assert "ignored" not in keys


# ── DB fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture()
def local_session():
    """In-memory SQLite session using LocalBase."""
    engine = create_engine("sqlite:///:memory:")
    LocalBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


# ── link_lecture_files ───────────────────────────────────────────────────────


class TestLinkLectureFiles:
    def test_empty_file_list(self, local_session) -> None:
        result = link_lecture_files([], local_session)
        assert isinstance(result, LinkResult)
        assert result.references_found == 0
        assert result.citations_found == 0

    def test_link_creates_citations(self, local_session, tmp_path: Path) -> None:
        """Citations are created in DB for \\cite{} macros."""
        tex = tmp_path / "a.tex"
        tex.write_text(r"\cite{serway2019}")

        # Register note first (linker requires note to exist)
        note = Note(filename=str(tex), reference="lect-tex-a")
        local_session.add(note)
        local_session.flush()

        result = link_lecture_files([tex], local_session)

        assert result.citations_found >= 1
        citations = list(local_session.scalars(select(Citation)).all())
        assert any(c.citationkey == "serway2019" for c in citations)

    def test_link_creates_labels(self, local_session, tmp_path: Path) -> None:
        """Label records are created for \\label{} macros."""
        tex = tmp_path / "b.tex"
        tex.write_text(r"\label{eq:gauss}")

        note = Note(filename=str(tex), reference="lect-tex-b")
        local_session.add(note)
        local_session.flush()

        link_lecture_files([tex], local_session)

        labels = list(local_session.scalars(select(Label)).all())
        assert any(lb.label == "eq:gauss" for lb in labels)

    def test_link_creates_links_for_refs(self, local_session, tmp_path: Path) -> None:
        """Link records are created when \\ref{} matches an existing Label."""
        # File A defines the label
        tex_a = tmp_path / "a.tex"
        tex_a.write_text(r"\label{eq:gauss}")
        note_a = Note(filename=str(tex_a), reference="lect-tex-a")
        local_session.add(note_a)
        local_session.flush()

        # File B references the label
        tex_b = tmp_path / "b.tex"
        tex_b.write_text(r"\ref{eq:gauss}")
        note_b = Note(filename=str(tex_b), reference="lect-tex-b")
        local_session.add(note_b)
        local_session.flush()

        result = link_lecture_files([tex_a, tex_b], local_session)

        links = list(local_session.scalars(select(Link)).all())
        assert len(links) >= 1
        assert result.links_created >= 1

    def test_link_idempotent_citations(self, local_session, tmp_path: Path) -> None:
        """Running link_lecture_files twice does not duplicate citations."""
        tex = tmp_path / "c.tex"
        tex.write_text(r"\cite{book1}")

        note = Note(filename=str(tex), reference="lect-tex-c")
        local_session.add(note)
        local_session.flush()

        link_lecture_files([tex], local_session)
        link_lecture_files([tex], local_session)

        citations = list(local_session.scalars(select(Citation)).all())
        assert len([c for c in citations if c.citationkey == "book1"]) == 1

    def test_link_idempotent_labels(self, local_session, tmp_path: Path) -> None:
        """Running link_lecture_files twice does not duplicate labels."""
        tex = tmp_path / "d.tex"
        tex.write_text(r"\label{sec:one}")

        note = Note(filename=str(tex), reference="lect-tex-d")
        local_session.add(note)
        local_session.flush()

        link_lecture_files([tex], local_session)
        link_lecture_files([tex], local_session)

        labels = list(local_session.scalars(select(Label)).all())
        assert len([lb for lb in labels if lb.label == "sec:one"]) == 1

    def test_link_returns_link_result(self, local_session, tmp_path: Path) -> None:
        tex = tmp_path / "e.tex"
        tex.write_text(r"\cite{ref1} \label{lb1}")

        note = Note(filename=str(tex), reference="lect-tex-e")
        local_session.add(note)
        local_session.flush()

        result = link_lecture_files([tex], local_session)

        assert isinstance(result, LinkResult)
        assert result.citations_found == 1
        assert result.references_found >= 1

    def test_ref_without_matching_label_adds_warning(
        self, local_session, tmp_path: Path
    ) -> None:
        """\\ref{} with no matching Label in DB produces a warning."""
        tex = tmp_path / "f.tex"
        tex.write_text(r"\ref{unknown:label}")

        note = Note(filename=str(tex), reference="lect-tex-f")
        local_session.add(note)
        local_session.flush()

        result = link_lecture_files([tex], local_session)

        assert len(result.warnings) >= 1
        assert any("unknown:label" in w for w in result.warnings)

    def test_file_not_in_db_skipped_with_warning(
        self, local_session, tmp_path: Path
    ) -> None:
        """Files not registered in DB as Notes produce a warning, not a crash."""
        tex = tmp_path / "orphan.tex"
        tex.write_text(r"\cite{something}")

        result = link_lecture_files([tex], local_session)

        assert len(result.warnings) >= 1

    def test_multiple_cites_in_one_file(self, local_session, tmp_path: Path) -> None:
        tex = tmp_path / "multi.tex"
        tex.write_text(r"\cite{a,b,c}")

        note = Note(filename=str(tex), reference="lect-tex-multi")
        local_session.add(note)
        local_session.flush()

        result = link_lecture_files([tex], local_session)

        assert result.citations_found == 3
        citations = list(local_session.scalars(select(Citation)).all())
        keys = {c.citationkey for c in citations}
        assert {"a", "b", "c"}.issubset(keys)
