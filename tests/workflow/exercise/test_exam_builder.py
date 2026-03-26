"""Tests for workflow.exercise.exam_builder — Exam assembly."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from workflow.db.models.exercises import Exercise
from workflow.exercise.exam_builder import ExamDocument, build_exam
from workflow.exercise.selector import ExerciseSlot, SelectionResult


def _make_exercise(
    exercise_id: str,
    source_path: str = "",
    taxonomy_level: str = "Recordar",
    taxonomy_domain: str = "Información",
) -> Exercise:
    ex = Exercise(
        exercise_id=exercise_id,
        source_path=source_path or f"/fake/{exercise_id}.tex",
        file_hash="abc123",
        status="complete",
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
    )
    return ex


def _make_selection(
    slot: ExerciseSlot,
    exercises: list[Exercise],
    unfilled: list[ExerciseSlot] | None = None,
    warnings: list[str] | None = None,
) -> SelectionResult:
    return SelectionResult(
        selected={slot: exercises},
        unfilled=unfilled or [],
        warnings=warnings or [],
    )


# ── ExamDocument type ────────────────────────────────────────────────────


def test_build_exam_basic():
    slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
    selection = SelectionResult(selected={slot: []}, unfilled=[], warnings=[])
    doc = build_exam(selection, title="My Exam")

    assert isinstance(doc, ExamDocument)
    assert doc.title == "My Exam"
    assert isinstance(doc.content, str)
    assert isinstance(doc.total_points, float)
    assert isinstance(doc.exercise_count, int)
    assert isinstance(doc.warnings, tuple)


def test_build_exam_reads_files():
    """build_exam reads .tex files and includes \\question content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "ex-001.tex"
        tex_path.write_text(
            r"""% ---
% id: ex-001
% status: complete
% ---
\question{
  What is $2+2$?
}{
  $4$
}
""",
            encoding="utf-8",
        )

        slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
        ex = _make_exercise("ex-001", source_path=str(tex_path))
        selection = _make_selection(slot, [ex])
        doc = build_exam(selection, title="Test")

        assert "2+2" in doc.content or "question" in doc.content.lower()
        assert doc.exercise_count == 1


def test_build_exam_total_points():
    """Total points = sum(slot.count * slot.points_per_item) for filled slots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex1 = Path(tmpdir) / "ex-001.tex"
        tex1.write_text(r"\question{stem}{sol}", encoding="utf-8")
        tex2 = Path(tmpdir) / "ex-002.tex"
        tex2.write_text(r"\question{stem}{sol}", encoding="utf-8")

        slot = ExerciseSlot("Recordar", "Información", count=2, points_per_item=15.0)
        exercises = [
            _make_exercise("ex-001", source_path=str(tex1)),
            _make_exercise("ex-002", source_path=str(tex2)),
        ]
        selection = _make_selection(slot, exercises)
        doc = build_exam(selection)

        assert doc.total_points == pytest.approx(30.0)
        assert doc.exercise_count == 2


def test_build_exam_missing_file_warns():
    """Exercise whose .tex file is missing produces a warning, not a crash."""
    slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
    ex = _make_exercise("ex-missing", source_path="/nonexistent/path/ex-missing.tex")
    selection = _make_selection(slot, [ex])
    doc = build_exam(selection)

    assert any("ex-missing" in w or "missing" in w.lower() for w in doc.warnings)
    assert doc.exercise_count == 0


def test_build_exam_empty_selection():
    """No exercises selected — minimal output, no crash."""
    selection = SelectionResult(selected={}, unfilled=[], warnings=[])
    doc = build_exam(selection, title="Empty Exam")

    assert doc.exercise_count == 0
    assert doc.total_points == 0.0
    assert isinstance(doc.content, str)


def test_build_exam_instructions_included():
    """Instructions string appears in the document content."""
    selection = SelectionResult(selected={}, unfilled=[], warnings=[])
    doc = build_exam(selection, title="Exam", instructions="Read carefully.")

    assert "Read carefully." in doc.content


def test_build_exam_multiple_slots():
    """Exercises from multiple slots all appear in document."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex1 = Path(tmpdir) / "ex-a.tex"
        tex1.write_text(r"\question{Alpha stem}{Alpha sol}", encoding="utf-8")
        tex2 = Path(tmpdir) / "ex-b.tex"
        tex2.write_text(r"\question{Beta stem}{Beta sol}", encoding="utf-8")

        slot_a = ExerciseSlot("Recordar", "Información", count=1, points_per_item=5.0)
        slot_b = ExerciseSlot(
            "Comprender", "Procedimiento Mental", count=1, points_per_item=10.0
        )
        ex_a = _make_exercise("ex-a", source_path=str(tex1))
        ex_b = _make_exercise("ex-b", source_path=str(tex2))
        selection = SelectionResult(
            selected={slot_a: [ex_a], slot_b: [ex_b]},
            unfilled=[],
            warnings=[],
        )
        doc = build_exam(selection, title="Multi-slot")

        assert doc.exercise_count == 2
        assert doc.total_points == pytest.approx(15.0)


def test_build_exam_warnings_immutable():
    """ExamDocument.warnings should be a tuple (immutable)."""
    doc = ExamDocument(
        title="Test", content="", total_points=0, exercise_count=0, warnings=()
    )
    assert isinstance(doc.warnings, tuple)
